import logging
import os
from pathlib import Path
import shutil
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

    def test_realToHumanFileSize(self):
        self.assertR2H(1234, "1.2K")
        self.assertH2R("1.2K", 1228)
        self.assertR2H(1132432, "1.1M")
        self.assertH2R("1.1M", 1153433)
        self.assertR2H(36345435, "34.7M")
        self.assertH2R("36.3M", 38063308)
        self.assertR2H(3634235435, "3.4G")
        self.assertH2R("3.6G", 3865470566)
        self.assertR2H(23634235435, "22.0G")
        self.assertH2R("23.6G", 25340307046)

    def assertR2H(self, integer, string):
        actual = FsTools.realToHumanFileSize(integer)
        self.assertEqual(string, actual)

    def assertH2R(self, string, integer):
        actual = FsTools.humanToRealFileSize(string)
        self.assertEqual(integer, actual)

    def test_hasEnoughFreeDiskSpace(self):
        self.assertTrue(FsTools.hasEnoughFreeDiskSpace("C:", "1M"))
        self.assertFalse(FsTools.hasEnoughFreeDiskSpace("C:", "1P")) # "should be enough for everybody "

    def test_copyFileToFile(self):
        parent = Path("copy_test")
        if parent.exists(): 
            shutil.rmtree(parent)
        parent.mkdir()
        srcFile = Path("copy_test/src_file.txt")
        srcFile.write_text("blabla")
        dstFile = Path("copy_test/target_file.txt")

        # file to file
        FsTools.copy(source=srcFile, destination=dstFile)
        self.assertTrue(dstFile.exists())
        shutil.rmtree(parent)

    def test_copyFileToDir(self):
        parent = Path("copy_test")
        if parent.exists(): 
            shutil.rmtree(parent)
        
        parent.mkdir()
        srcFile = Path("copy_test/src_file.txt")
        srcFile.write_text("blabla")
        dstDir = Path("copy_test/targetDir")
        dstDir.mkdir()

        # file to file
        FsTools.copy(source=srcFile, destination=dstDir)
        self.assertTrue(Path(f"{dstDir}/src_file.txt").exists())
        shutil.rmtree(parent)



    def test_copyDirToFile(self):
        parent = Path("copy_test")
        if parent.exists(): 
            shutil.rmtree(parent)
        
        parent.mkdir()
        srcDir = Path("copy_test/src_dir")
        srcDir.mkdir()
        dstFile = Path("copy_test/target_file.txt")
        dstFile.write_text("omg")

        # file to file SHOULD FAIL!
        with self.assertRaises(FileExistsError) as context:
            FsTools.copyDir(source=srcDir, destination=dstFile)
        shutil.rmtree(parent)

    def test_copyDirToDir(self):
        parent = Path("copy_test")
        if parent.exists(): 
            shutil.rmtree(parent)
        
        parent.mkdir()
        srcDir = Path("copy_test/src_dir")
        srcDir.mkdir()
        srcDirFile = Path("copy_test/src_dir/file2.txt")
        srcDirFile.write_text("bar")
        dstDir = Path("copy_test/target_dir")

        # file to file
        FsTools.copyDir(source=srcDir, destination=dstDir)
        self.assertTrue(Path("copy_test/target_dir/file2.txt").exists())
        shutil.rmtree(parent)

    def test_copyDirToDirTargetExists(self):
        parent = Path("copy_test")
        if parent.exists(): 
            shutil.rmtree(parent)
        
        parent.mkdir()
        srcDir = Path("copy_test/src_dir")
        srcDir.mkdir()
        srcDirFile = Path("copy_test/src_dir/file2.txt")
        srcDirFile.write_text("bar")
        dstDir = Path("copy_test/target_dir")
        dstDir.mkdir()

        # file to file
        FsTools.copyDir(source=srcDir, destination=dstDir)
        self.assertTrue(Path("copy_test/target_dir/src_dir/file2.txt").exists())
        shutil.rmtree(parent)

    def test_isGlobPattern(self):
        self.assertFalse(FsTools.isGlobPattern("D:\EGS\Empyrion"))
        self.assertTrue(FsTools.isGlobPattern("D:\EGS\Empyrion\*"))
        self.assertFalse(FsTools.isGlobPattern("D:\EGS\Empyrion\bla.txt"))
        self.assertFalse(FsTools.isGlobPattern("some/path"))
        self.assertTrue(FsTools.isGlobPattern("some/path/with/**/glob/stuff/*.dat"))
        self.assertFalse(FsTools.isGlobPattern("some/path/with/no/glob/stuff.txt"))

        self.assertTrue(FsTools.isGlobPattern("D:/some/path/*.txt"))
        self.assertFalse(FsTools.isGlobPattern("D:/some/path/foo.txt"))

    def test_resolveGlobbedPatternsAndExtendWithAbsolute(self):
        userentries = [
            "d:/egs/empyrion/esm/requirements.txt",
            "d:/egs/empyrion/b*.txt",
            "esm/esm-config.*",
            "esm/*.toml"
            ]
        expected = [
            "d:/egs/empyrion/buildnumber.txt",
            "d:/egs/empyrion/esm/esm-config.yaml",
            "d:/egs/empyrion/esm/pyproject.toml",
            "d:/egs/empyrion/esm/requirements.txt"
            ]
        
        parentDir = Path("D:/EGS/Empyrion").absolute()

        absoluteEntries = FsTools.toAbsolutePaths(userentries, parentDir)
        for entry in absoluteEntries:
            log.debug(f"absolute: {entry}")
            self.assertTrue(entry.is_absolute())
        
        deglobbedEntries = FsTools.resolveGlobs(absoluteEntries)
        result = []
        for entry in deglobbedEntries:
            result.append(str(entry).lower())
        self.assertListEqual(sorted(expected), sorted(result))
