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
        self.assertEqual(stoptime, datetime(year=2023, month=10, day=17, hour=19, minute=00, second=50, microsecond=0))