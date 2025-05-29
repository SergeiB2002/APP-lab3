# APP-lab3
Мультиагентное приложение для размещения заказов на оборудование

Тема: Разработка мультиагентного приложения с реактивной архитектурой

1. Описание агента-модели:
   - Типы агентов:
     * FirmAgent — агент фирмы-заказчика
     * ManufacturerAgent — агент завода-изготовителя
   - Поведение (Behaviour): реактивное, на основе событий сообщений FIPA (CFP, PROPOSE, ACCEPT, REJECT)
   - Состояния агентов:
     FirmAgent: отправил CFP -> ожидает предложений -> выбрал поставщика -> завершил
     ManufacturerAgent: ожидает CFP -> получил CFP -> проверил критерии -> отправил PROPOSE или не отвечает

2. Интерфейсы взаимодействия:
   - Сообщения FIPA-ACL:
     * CFP (Call for Proposal): от FirmAgent ко всем ManufacturerAgent
       - content: JSON {"product": "equipment", "requirements": {"cost": v1, "productivity": v2, "reliability": v3}}
     * PROPOSE: от ManufacturerAgent к FirmAgent
       - content: JSON {"manufacturer": name, "offer": {"cost": v1, "productivity": v2, "reliability": v3}}
     * ACCEPT-PROPOSAL / REJECT-PROPOSAL: от FirmAgent к каждому ManufacturerAgent
       - content: {"order": accepted or rejected}

Требования: Python 3.8+, spade
