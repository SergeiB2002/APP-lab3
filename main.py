import asyncio
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.template import Template

global_monitor_jid = "monitor@localhost"


class MonitorCopyBehaviour(OneShotBehaviour):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg

    async def run(self):
        await self.send(self.msg)
        self.kill()


manufacturers_info = {
    "Photon":    {"jid": "photon@localhost",    "password": "photonpwd",    "offer": {"cost": 5, "productivity": 120, "reliability": 9}},
    "Specdetal": {"jid": "specdetal@localhost", "password": "specpwd",     "offer": {"cost": 8, "productivity": 200, "reliability": 7}},
    "Stankostroy": {"jid": "stank@localhost",  "password": "stankpwd",   "offer": {"cost": 5, "productivity": 100, "reliability": 8}},
    "Atom":      {"jid": "atom@localhost",      "password": "atompwd",     "offer": {"cost": 7, "productivity": 150, "reliability": 6}},
}

manufacturers = {}
display_to_jid = {}
for disp, data in manufacturers_info.items():
    user = data["jid"].split("@")[0]
    manufacturers[user] = {"jid": data["jid"], "password": data["password"], "offer": data["offer"], "display": disp}
    display_to_jid[disp] = data["jid"]

firms = {
    "firm1": {"jid": "firm1@localhost", "password": "firm1pwd", "requirements": {"cost": 5, "productivity": 100, "reliability": 8}},
    "firm2": {"jid": "firm2@localhost", "password": "firm2pwd", "requirements": {"cost": 6, "productivity": 150, "reliability": 5}},
}


class ManufacturerAgent(Agent):
    class CFPReceiver(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg and msg.get_metadata("performative") == "cfp":
                print(f"[{self.agent.display}] CFP получен от {msg.sender}")
                req = json.loads(msg.body).get("requirements")
                offer = self.agent.offer
                if offer["cost"] <= req["cost"] and offer["productivity"] >= req["productivity"] and offer["reliability"] >= req["reliability"]:
                    reply = Message(to=str(msg.sender))
                    reply.set_metadata("performative", "propose")
                    reply.body = json.dumps({"manufacturer": self.agent.display, "offer": offer})
                    await self.send(reply)
                    print(f"[{self.agent.display}] PROPOSE отправлен к {msg.sender}: {offer}")
                    monitor_msg = Message(to=global_monitor_jid)
                    monitor_msg.set_metadata("performative", "inform")
                    monitor_msg.body = f"[{self.agent.display}] PROPOSE to={msg.sender} body={reply.body}"
                    self.agent.add_behaviour(MonitorCopyBehaviour(monitor_msg))
                else:
                    print(f"[{self.agent.display}] Требования не выполнены, PROPOSE не отправлен")

    class ResponseReceiver(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                perf = msg.get_metadata("performative")
                print(f"[{self.agent.display}] Получен {perf.upper()} от {msg.sender}: {msg.body}")

    async def setup(self):
        user = self.jid.user
        info = manufacturers[user]
        self.display = info["display"]
        self.offer = info["offer"]
        tpl = Template()
        tpl.set_metadata("performative", "cfp")
        self.add_behaviour(self.CFPReceiver(), tpl)
        tpl_acc = Template()
        tpl_acc.set_metadata("performative", "accept-proposal")
        self.add_behaviour(self.ResponseReceiver(), tpl_acc)
        tpl_rej = Template()
        tpl_rej.set_metadata("performative", "reject-proposal")
        self.add_behaviour(self.ResponseReceiver(), tpl_rej)
        print(f"[{self.display}] запущен, предложение={self.offer}")


class FirmAgent(Agent):
    class CFPDispatcher(OneShotBehaviour):
        async def run(self):
            print(f"[{self.agent.display}] отправка CFP")
            for info in manufacturers.values():
                cfp = Message(to=info["jid"])
                cfp.set_metadata("performative", "cfp")
                cfp.body = json.dumps({"product": "equipment", "requirements": self.agent.requirements})
                await self.send(cfp)
                print(f"[{self.agent.display}] CFP отправлен к {info['jid']}")
                monitor_cfp = Message(to=global_monitor_jid)
                monitor_cfp.set_metadata("performative", "inform")
                monitor_cfp.body = f"[{self.agent.display}] CFP to={info['jid']} body={cfp.body}"
                self.agent.add_behaviour(MonitorCopyBehaviour(monitor_cfp))
            self.agent.add_behaviour(self.agent.Collector())

    class Collector(CyclicBehaviour):
        async def on_start(self):
            import time
            self.proposals = []
            self.start_time = time.monotonic()
            print(f"[{self.agent.display}] Начало сбора предложений")

        async def run(self):
            import time
            msg = await self.receive(timeout=1)
            if msg and msg.get_metadata("performative") == "propose":
                prop = json.loads(msg.body)
                self.proposals.append(prop)
                print(f"[{self.agent.display}] PROPOSE получен от {prop['manufacturer']}: {prop['offer']}")
                monitor_prop = Message(to=global_monitor_jid)
                monitor_prop.set_metadata("performative", "inform")
                monitor_prop.body = f"[{self.agent.display}] PROPOSE from={prop['manufacturer']} body={msg.body}"
                self.agent.add_behaviour(MonitorCopyBehaviour(monitor_prop))
            if time.monotonic() - self.start_time > 5:
                print(f"[{self.agent.display}] Сбор завершён, предложений: {len(self.proposals)}")
                if not self.proposals:
                    print(f"[{self.agent.display}] Нет подходящих предложений")
                else:
                    best = min(self.proposals, key=lambda p: p['offer']['cost'])
                    print(f"[{self.agent.display}] Выбрано: {best['manufacturer']} с {best['offer']}")
                    for p in self.proposals:
                        perform = 'accept-proposal' if p['manufacturer'] == best['manufacturer'] else 'reject-proposal'
                        action = 'ACCEPT' if p['manufacturer'] == best['manufacturer'] else 'REJECT'
                        reply = Message(to=display_to_jid[p['manufacturer']])
                        reply.set_metadata("performative", perform)
                        reply.body = json.dumps({"order": action.lower()})
                        await self.send(reply)
                        print(f"[{self.agent.display}] {action}-PROPOSAL отправлен к {p['manufacturer']}")
                        monitor_reply = Message(to=global_monitor_jid)
                        monitor_reply.set_metadata("performative", "inform")
                        monitor_reply.body = f"[{self.agent.display}] {action.upper()} to={p['manufacturer']} body={reply.body}"
                        self.agent.add_behaviour(MonitorCopyBehaviour(monitor_reply))
                self.kill()

    async def setup(self):
        user = self.jid.user
        info = firms[user]
        self.display = user
        self.requirements = info['requirements']
        print(f"[{self.display}] запущен, требования={self.requirements}")
        tmpl = None
        self.add_behaviour(self.CFPDispatcher(), tmpl)


class MonitorAgent(Agent):
    class Sniffer(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                self.agent.log_file.write(msg.body + '\n')
                self.agent.log_file.flush()
    async def setup(self):
        self.log_file = open('monitor.log', 'a', encoding='utf-8')
        tmpl = Template()
        self.add_behaviour(self.Sniffer(), tmpl)
        self.log_file.write("[Monitor] Sniffer started\n")
        self.log_file.flush()


async def main():
    agents = []
    agents.append(MonitorAgent(global_monitor_jid, "monitorpwd"))
    for info in manufacturers.values():
        agents.append(ManufacturerAgent(info['jid'], info['password']))
    for info in firms.values():
        agents.append(FirmAgent(info['jid'], info['password']))

    base_port = 10000
    for idx, agent in enumerate(agents):
        await agent.start(auto_register=True)
        port = str(base_port + idx)
        agent.web.start(hostname='127.0.0.1', port=port)
        print(f"[{agent.jid.user}] Web interface started at http://127.0.0.1:{port}/spade")
    print("Все агенты запущены")
    await asyncio.sleep(60)
    for agent in agents:
        await agent.stop()
    print("Все агенты остановлены")

if __name__ == '__main__':
    asyncio.run(main())

