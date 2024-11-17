
import logging
import time
import unittest
from unittest.mock import patch

from esm.DataTypes import ChatMessage
from esm.EsmHaimsterConnector import EsmHaimsterConnector
from esm.EsmLogger import EsmLogger
from esm.ServiceRegistry import ServiceRegistry
from fastapi.testclient import TestClient

EsmLogger.setUpLogging(streamLogLevel=logging.DEBUG)
log = logging.getLogger(__name__)

class test_EsmHaimsterConnector(unittest.TestCase):

    def test_getServiceFromRegistry(self):
        hc = ServiceRegistry.get(EsmHaimsterConnector)
        self.assertIsNotNone(hc)

    @patch("esm.EsmEmpRemoteClientService.EsmEmpRemoteClientService.emprcExecute", autospec=True)
    def test_StartsUp(self, mock_emprcExecute):
        hc = ServiceRegistry.get(EsmHaimsterConnector)
        hc.initialize()
        hc.sendOutgoingChatResponse(ChatMessage(speaker="hAImster", message="connected!", timestamp=time.time()))
        hc.shutdown()

    def test_endpoint(self):
        hc = ServiceRegistry.get(EsmHaimsterConnector)
        hc.initialize()
        client = TestClient(hc._fastApiApp)
        response =client.post("/outgoingmessage", json={"speaker": "hAImster", "message": "connected!", "timestamp": time.time()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        hc.shutdown()

