import backend as b
import os
import getpass
import shutil

localuser = str(getpass.getuser())
modsDir = f'C:/Users/{localuser}/AppData/Roaming/.minecraft/mods/'

def deleteOnlyJar(path):
    files = os.listdir(path)
    for i in files:
        if ".jar" in i:
            os.remove(path + "/" + i)

def copyAllJars(version):
    shutil.copytree(f"{modsDir}{version}", modsDir, dirs_exist_ok=True)

'''
You'll want to change these versions to whatever suits your needs
'''

print("================================================")
print("1) LabyMod")
print("2) Fabric 1.17")
print("================================================")

choice = input("Please choose a version from above: ")

if choice == "1":
    deleteOnlyJar(modsDir)
    copyAllJars("1.8")
    b.launch("1.8.9-forge1.8.9-11.15.1.2318-1.8.9", javaVersion=r"C:\Program Files\Java\jre1.8.0_291\bin\java.exe")
if choice == "2":
    deleteOnlyJar(modsDir)
    copyAllJars("1.17")
    b.launch("fabric-loader-0.11.6-1.17")