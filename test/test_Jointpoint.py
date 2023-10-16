import logging
import os
from pathlib import Path
import subprocess
import unittest
from esm.EsmConfig import EsmConfig
from esm.FsTools import FsTools

log = logging.getLogger(__name__)

class test_Jointpoint(unittest.TestCase):

    def test_create(self):
        target = Path("test-linktarget")
        link = Path("test-link")
        # make sure its cleaned up first
        self.cleanTestFolders(target, link)

        self.assertFalse(target.exists())
        self.assertFalse(link.exists())
        
        target.mkdir()
        FsTools.createLink(linkPath=link, targetPath=target)
        
        self.assertTrue(target.exists())
        self.assertTrue(link.exists())

        #subprocess.run("rmdir /S /Q test-link", shell=True)
        # clean up
        self.cleanTestFolders(target, link)

    def test_delete(self):
        target = Path("test-linktarget")
        link = Path("test-link")
        # make sure its cleaned up first
        self.cleanTestFolders(target, link)

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
        self.cleanTestFolders(target, link)

    def test_isHardLink(self):
        target = Path("test-linktarget")
        link = Path("test-link")
        # make sure its cleaned up first
        self.cleanTestFolders(target, link)

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
        self.cleanTestFolders(target, link)

    def cleanTestFolders(self, target, link):
        if link.exists():
            if link.is_dir():
                link.rmdir()
            else:
                os.unlink(link)
                link.unlink(missing_ok=True)
        if target.exists(): 
            target.rmdir()


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


