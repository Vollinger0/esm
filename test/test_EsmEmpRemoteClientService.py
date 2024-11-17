
import logging
import time
import unittest

from esm.EsmEmpRemoteClientService import Channel, EsmEmpRemoteClientService, Priority, SenderType
from esm.ServiceRegistry import ServiceRegistry


log = logging.getLogger(__name__)

@unittest.skip("only for manual execution, since you won't see anything if you aren't looking ingame.")
class test_EsmEmpRemoteClientService(unittest.TestCase):

    def test_serverChatAndAnnouncements(self):
        emprc = ServiceRegistry.get(EsmEmpRemoteClientService)
        # no way to assert this, start the game and look at the chat.
        emprc.sendServerChat(message=f"hello from esm, dear watcher of the server chat!", quietMode=False)
        time.sleep(2)
        emprc.sendAnnouncement(message="alert from an esm test", priority=Priority.ALERT, quietMode=False)
        time.sleep(2)
        emprc.sendAnnouncement(message="warning from an esm test", priority=Priority.WARNING, quietMode=False)
        time.sleep(2)
        emprc.sendAnnouncement(message="info from an esm test", priority=Priority.INFO, quietMode=False)
        time.sleep(2)
        emprc.sendAnnouncement(message="just some text from an esm test", priority=Priority.OTHER, quietMode=False)
        time.sleep(2)
        emprc.sendMessage(senderName="The first tester", message="woohooo! test succeeded!")
        time.sleep(2)
        emprc.sendMessage(senderName="The[0affe0]colored[deadbe]Tester", message="[78ab56]so[ab5678]many[5678ab]colors")
        time.sleep(2)
        self.debugSend(emprc)
        

    def debugSend(self, emprc: EsmEmpRemoteClientService):
        emprc.sendMessage(senderName="SendertypeShowcase", message="*all sender types and no sender name*")
        for senderType in SenderType:
            emprc.sendMessage(message=f"i am senderType {senderType}", senderType=senderType)
            time.sleep(.3)
        emprc.sendMessage(senderName="SendertypeShowcase", message="*sending all sender types with set name*")
        for senderType in SenderType:
            emprc.sendMessage(senderName="FooBar", message=f"i am senderType {senderType}", senderType=senderType)
            time.sleep(.3)
        emprc.sendMessage(senderName="ChanneltypeShowcase", message="*sending at all channel types*")
        for channel in Channel:
            emprc.sendMessage(senderName="Tester2", message=f"i am channel type {channel}", channel=channel)
            time.sleep(.3)

    def test_manual(self):
        emprc = ServiceRegistry.get(EsmEmpRemoteClientService)
        emprc.sendMessage(senderName="[0fa336]Hamster-AI", message="[aaaaaa]asdf adf asdf sd f")
