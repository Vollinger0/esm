import logging
import os
from pathlib import Path
import unittest
from esm.FsTools import FsTools

log = logging.getLogger(__name__)

class test_FsTools(unittest.TestCase):

    def test_createLink(self):
        target = Path("test-linktarget")
        link = Path("test-link")
        # make sure its cleaned up first
        self.cleanTestFolders([target, link])

        self.assertFalse(target.exists())
        self.assertFalse(link.exists())
        
        target.mkdir()
        FsTools.createLink(linkPath=link, targetPath=target)
        
        self.assertTrue(target.exists())
        self.assertTrue(link.exists())

        #subprocess.run("rmdir /S /Q test-link", shell=True)
        # clean up
        self.cleanTestFolders([target, link])

    def test_deleteLink(self):
        target = Path("test-linktarget")
        link = Path("test-link")
        # make sure its cleaned up first
        self.cleanTestFolders([target, link])

        self.assertFalse(target.exists())
        self.assertFalse(link.exists())
        
        target.mkdir()
        FsTools.createLink(linkPath=link, targetPath=target)
        
        self.assertTrue(target.exists())
        self.assertTrue(link.exists())

        FsTools.deleteLink(link)

        self.assertTrue(target.exists())
        self.assertFalse(link.exists())

        #subprocess.run("rmdir /S /Q test-link", shell=True)
        # clean up
        self.cleanTestFolders([target, link])

    def test_isHardLink(self):
        target = Path("test-linktarget")
        link = Path("test-link")
        # make sure its cleaned up first
        self.cleanTestFolders([target, link])

        self.assertFalse(target.exists())
        self.assertFalse(link.exists())
        
        target.mkdir()
        FsTools.createLink(linkPath=link, targetPath=target)
        
        self.assertTrue(target.exists())
        self.assertTrue(link.exists())

        resultlink = FsTools.isHardLink(link)
        resultdir = FsTools.isHardLink(target)

        self.assertTrue(resultlink)
        self.assertFalse(resultdir)

        # clean up
        self.cleanTestFolders([target, link])

    def cleanTestFolders(self, dirs):
        for dir in dirs:
            if dir.exists():
                if dir.is_dir():
                    dir.rmdir()
                else:
                    os.unlink(dir)
                    dir.unlink(missing_ok=True)
            else:
                if FsTools.isHardLink(dir):
                    FsTools.deleteLink(dir)

    def test_multipleLinks(self):
        target1 = Path("test-linktarget1")
        target2 = Path("test-linktarget2")
        link1 = Path("test-link1")
        link2 = Path("test-link2")
        link3 = Path("test-link3")
        link4 = Path("test-link4")
        # make sure its cleaned up first
        dirs = [link1, link2, link3, link4, target1, target2]
        self.cleanTestFolders(dirs)

        for dir in dirs:
            self.assertFalse(dir.exists())

        target1.mkdir()
        target2.mkdir()
        FsTools.createLink(linkPath=link1, targetPath=target1)
        FsTools.createLink(linkPath=link2, targetPath=target1)
        FsTools.createLink(linkPath=link3, targetPath=target2)
        FsTools.createLink(linkPath=link4, targetPath=target2)
        
        for dir in dirs:
            self.assertTrue(dir.exists())

        self.assertTrue(FsTools.isHardLink(link1))
        self.assertTrue(FsTools.isHardLink(link2))
        self.assertTrue(FsTools.isHardLink(link3))
        self.assertTrue(FsTools.isHardLink(link4))
        self.assertFalse(FsTools.isHardLink(target1))
        self.assertFalse(FsTools.isHardLink(target2))

        # log.debug(f"os.readlink(link1) {os.readlink(link1)}")
        # log.debug(f"Path.readlink(link1) {Path.readlink(link1)}")
        # log.debug(f"link1.readlink() {link1.readlink()}")
        # for entry in dirs:
        #     if FsTools.isHardLink(entry):
        #         linkInfo = entry.readlink().resolve()
        #         fixedLinkInfo = Path(linkInfo.as_posix()[4:])
        #         log.debug(f"linktarget of {entry}, {linkInfo} -> {fixedLinkInfo} and {target1} are the same file")
        #         # if (linkInfo.as_posix().endswith(target1.name)):
        #         #     log.debug(f"link {entry} points to the requested target {target1}")
        #         # if (linkInfo.as_posix().endswith(Path(target1).as_posix())):
        #         #     log.debug(f"link {entry} points to the requested resolved target {target1}")
        #         if fixedLinkInfo.exists:
        #             if (fixedLinkInfo.samefile(target1.resolve())):
        #                 log.debug(f"linktarget of {entry}, {fixedLinkInfo} and {target1} are the same file")

        # the actual method we want to test ;)
        links = FsTools.getLinksToTarget(directory=Path("."), targetFolder=target1)
        # self.assertEqual(links, [link1.absolute(), link2.absolute()])
        self.assertListEqual(links, [link1, link2])

        # clean up
        self.cleanTestFolders(dirs)

    # def testCreateWithDifferentLibs(self):
    #     target = Path("test-linktarget")
    #     link = Path("test-link")
    #     # make sure its cleaned up first
    #     self.cleanTestFolders(target, link)

    #     self.assertFalse(target.exists())
    #     self.assertFalse(link.exists())
        
    #     target.mkdir()
    #     Jointpoint.create(link=link, target=target)

    #     # works perfectly.
    #     #subprocess.run(f"mklink /H /J {link} {target}", capture_output=True, shell=True)

    #     # doesn't work
    #     #os.link(src=link, dst=target)
    #     #os.link(src=target, dst=link)
    #     #Path(target).link_to(Path(link))
    #     #Path(link).link_to(Path(target))
    #     #Path(target).hardlink_to(Path(link))
    #     #Path(link).hardlink_to(Path(target))
    #     # import win32file
    #     # win32file.CreateHardLink("test-link", "test-linktarget")
    #     #esmfs.createJointpoint(linkTarget=link, link=target)
        
    #     self.assertTrue(target.exists())
    #     self.assertTrue(link.exists())

    #     #subprocess.run("rmdir /S /Q test-link", shell=True)
    #     # clean up
    #     self.cleanTestFolders(target, link)


