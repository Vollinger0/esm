from datetime import datetime
import logging
from pathlib import Path
import unittest

from esm.EsmDatabaseWrapper import EsmDatabaseWrapper

log = logging.getLogger(__name__)

class test_EsmDatabaseWrapper(unittest.TestCase):

    def test_retrieveCurrentGametick(self):
        dbPath = Path(f"./test/test.db").resolve()
        db = EsmDatabaseWrapper(dbPath)
        timetick, stoptime = db.retrieveLatestGametime()
        log.debug(f"timetick: {timetick}")
        log.debug(f"stoptime: {stoptime}")

        # 351813
        self.assertEqual(timetick, 351813)
        # 2023-10-17 19:00:50
        dateFormat = '%Y-%m-%d %H:%M:%S'
        expected = datetime.strptime("2023-10-17 19:00:50", dateFormat)
        self.assertEqual(expected, stoptime)

    def test_retrieveLatestGameStoptickWithinDatetime(self):
        dbPath = Path(f"./test/test.db").resolve()
        db = EsmDatabaseWrapper(dbPath)
        dateFormat = '%Y-%m-%d %H:%M:%S'

        # input: a rough date
        # output: a gametick that corresponds to the date or lower.

        #31	334552	338320	2023-10-17 00:14:04	2023-10-17 00:17:14
        inputtime = datetime.strptime("2023-10-17 00:15:14", dateFormat)
        expectedTick = 334552
        timetick, stoptime = db.retrieveLatestGameStoptickWithinDatetime(inputtime)
        self.assertEqual(expectedTick, timetick)

        # 34	341747	351813	2023-10-17 18:52:23	2023-10-17 19:00:50	v1.10.4	4243	+02:00        
        inputtime = datetime.strptime("2023-10-17 18:55:14", dateFormat)
        expectedTick = 341747
        timetick, stoptime = db.retrieveLatestGameStoptickWithinDatetime(inputtime)
        self.assertEqual(expectedTick, timetick)

        # 32	338320	339404	2023-10-17 00:31:57	2023-10-17 00:32:53	v1.10.4	4243	+02:00
        # 33	339404	341747	2023-10-17 00:34:11	2023-10-17 00:36:11	v1.10.4	4243	+02:00
        # somewhere between two server running periods
        inputtime = datetime.strptime("2023-10-17 00:33:00", dateFormat)
        expectedTick = 339404
        timetick, stoptime = db.retrieveLatestGameStoptickWithinDatetime(inputtime)
        self.assertEqual(expectedTick, timetick)

        # somewhere in the past before the first line
        inputtime = datetime.strptime("2021-10-17 18:55:14", dateFormat)
        expectedTick = 0
        timetick, stoptime = db.retrieveLatestGameStoptickWithinDatetime(inputtime)
        self.assertEqual(expectedTick, timetick)

        # somewhere in the future after the last line
        inputtime = datetime.now()
        expectedTick = 351813
        timetick, stoptime = db.retrieveLatestGameStoptickWithinDatetime(inputtime)
        self.assertEqual(expectedTick, timetick)

    def test_retrievePFsUnvisitedSince(self):
        dbPath = Path(f"./test/test.db").resolve()
        db = EsmDatabaseWrapper(dbPath)

        pfs = db.retrievePFsUnvisitedSince(336776)
        pfIds = list(map(lambda pf: pf.pfid, pfs))
        self.assertEqual(len(pfs), 2)
        self.assertEqual(sorted(pfIds), [88, 709])


    def test_retrieveNonRemovedEntities(self):
        dbPath = Path(f"./test/test.db").resolve()
        db = EsmDatabaseWrapper(dbPath)

        pfIds = db.retrieveNonRemovedEntities()
        self.assertEqual(len(pfIds), 213)

    def test_retrieve_PlayerNames(self):
        dbPath = Path(f"./test/test.db").resolve()
        db = EsmDatabaseWrapper(dbPath)

        playerEntities = db.retrieveAllPlayerEntities()
        self.assertEqual(len(playerEntities), 6)
        self.assertEqual(playerEntities.get(16142), "Vollinger")

    def test_export_chatlog(self):
        dbPath = Path(f"./test/test.db").resolve()
        db = EsmDatabaseWrapper(dbPath)
        chatlog = db.retrieveFullChatlog()
        self.assertEqual(len(chatlog), 16)
        self.assertEqual(chatlog[10]['timestamp'], 1696969083.644768)
        self.assertEqual(chatlog[10]['speaker'], "Vollinger")
        self.assertEqual(chatlog[10]['message'], "cb:restart")
