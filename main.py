import asyncio
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.template import Template

# Данные по производителям
manufacturers_info = {
    "Photon":    {"jid": "photon@localhost",    "password": "photonpwd",    "offer": {"cost": 5, "productivity": 120, "reliability": 9}},
    "Specdetal": {"jid": "specdetal@localhost", "password": "specpwd",     "offer": {"cost": 8, "productivity": 200, "reliability": 7}},
    "Stankostroy": {"jid": "stank@localhost",  "password": "stankpwd",   "offer": {"cost": 5, "productivity": 100, "reliability": 8}},
    "Atom":      {"jid": "atom@localhost",      "password": "atompwd",     "offer": {"cost": 7, "productivity": 150, "reliability": 6}},
}
# Построение словарей по user и отображению
manufacturers = {}
display_to_jid = {}
for disp, data in manufacturers_info.items():
    user = data["jid"].split("@")[0]
    manufacturers[user] = {"jid": data["jid"], "password": data["password"], "offer": data["offer"], "display": disp}
    display_to_jid[disp] = data["jid"]

# Данные по фирмам
firms = {
    "firm1": {"jid": "firm1@localhost", "password": "firm1pwd", "requirements": {"cost": 5, "productivity": 100, "reliability": 8}},
    "firm2": {"jid": "firm2@localhost", "password": "firm2pwd", "requirements": {"cost": 6, "productivity": 150, "reliability": 5}},
}

class ManufacturerAgent(Agent):
    class CFPReceiver(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg and msg.get_metadata("performative") == "cfp":
                print(f"[{self.agent.display}] Получен CFP от {msg.sender}")
                req = json.loads(msg.body).get("requirements")
                offer = self.agent.offer
                if offer["cost"] <= req["cost"] and offer["productivity"] >= req["productivity"] and offer["reliability"] >= req["reliability"]:
                    reply = Message(to=str(msg.sender))
                    reply.set_metadata("performative", "propose")
                    reply.body = json.dumps({"manufacturer": self.agent.display, "offer": offer})
                    await self.send(reply)
                    print(f"[{self.agent.display}] PROPOSE отправлен -> {msg.sender}: {offer}")
                else:
                    print(f"[{self.agent.display}] Требования не выполнены, PROPOSE не отправлен")
    async def setup(self):
        user = self.jid.user
        info = manufacturers[user]
        self.display = info["display"]
        self.offer = info["offer"]
        tpl = Template()
        tpl.set_metadata("performative", "cfp")
        self.add_behaviour(self.CFPReceiver(), tpl)
        print(f"[{self.display}] Запущен, offer={self.offer}")

class FirmAgent(Agent):
    class CFPDispatcher(OneShotBehaviour):
        async def run(self):
            print(f"[{self.agent.display}] Рассылка CFP всем производителям")
            for info in manufacturers.values():
                cfp = Message(to=info["jid"])
                cfp.set_metadata("performative", "cfp")
                cfp.body = json.dumps({"product": "equipment", "requirements": self.agent.requirements})
                await self.send(cfp)
                print(f"[{self.agent.display}] CFP отправлен -> {info['jid']}")
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
                        print(f"[{self.agent.display}] {action}-PROPOSAL отправлен {p['manufacturer']}")
                self.kill()
    async def setup(self):
        user = self.jid.user
        info = firms[user]
        self.display = user
        self.requirements = info['requirements']
        print(f"[{self.display}] Запущен, requirements={self.requirements}")
        self.add_behaviour(self.CFPDispatcher(), None)

class MonitorAgent(Agent):
    class Sniffer(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                log_line = (
                    f"[Monitor] {msg.sender} -> {msg.to} | perf={msg.metadata.get('performative')} | body={msg.body}\n"
                )
                self.agent.log_file.write(log_line)
                self.agent.log_file.flush()
    async def setup(self):
        # Открываем файл для логирования
        self.log_file = open('monitor.log', 'a', encoding='utf-8')
        tpl = Template()
        self.add_behaviour(self.Sniffer(), tpl)
        self.log_file.write("[Monitor] Sniffer started, logging all messages to monitor.log\n")
        self.log_file.flush()

async def main():
    agents = []
    # Монитор
    agents.append(MonitorAgent("monitor@localhost", "monitorpwd"))
    # Производители
    for info in manufacturers.values():
        agents.append(ManufacturerAgent(info['jid'], info['password']))
    # Фирмы
    for info in firms.values():
        agents.append(FirmAgent(info['jid'], info['password']))

    # Запуск агентов и веб-интерфейсов
    base_port = 10000
    for idx, agent in enumerate(agents):
        await agent.start(auto_register=True)
        try:
            agent.web.start(hostname='127.0.0.1', port=str(base_port+idx))
            print(f"[{agent.jid.user}] Web UI: http://127.0.0.1:{base_port+idx}")
        except Exception:
            pass
    print("Все агенты и монитор запущены.")

    # Работа в течение 30 секунд
    await asyncio.sleep(30)

    # Остановка агентов
    for agent in agents:
        await agent.stop()
    print("Все агенты и монитор остановлены.")

if __name__ == '__main__':
    asyncio.run(main())
