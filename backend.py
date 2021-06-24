import json
import os
import platform
from pathlib import Path
import getpass
import subprocess as sp
import requests
import uuid
import sys

def libraryCheck(lib):
    def rule_says_yes(rule):
        useLib = None

        if rule["action"] == "allow":
            useLib = False
        elif rule["action"] == "disallow":
            useLib = True

        if "os" in rule:
            for key, value in rule["os"].items():
                os = platform.system()
                if key == "name":
                    if value == "windows" and os != 'Windows':
                        return useLib
                    elif value == "osx" and os != 'Darwin':
                        return useLib
                    elif value == "linux" and os != 'Linux':
                        return useLib
                elif key == "arch":
                    if value == "x86" and platform.architecture()[0] != "32bit":
                        return useLib

        return not useLib

    if not "rules" in lib:
        return True

    shouldUseLibrary = False
    for i in lib["rules"]:
        if rule_says_yes(i):
            return True

    return shouldUseLibrary

def getNatives(lib):
    arch = ""
    if platform.architecture()[0] == "64bit":
        arch = "64"
    elif platform.architecture()[0] == "32bit":
        arch = "32"
    else:
        raise Exception("Architecture not supported")

    nativesFile=""
    if not "natives" in lib:
        return nativesFile

    if "windows" in lib["natives"] and platform.system() == 'Windows':
        nativesFile = lib["natives"]["windows"].replace("${arch}", arch)
    elif "osx" in lib["natives"] and platform.system() == 'Darwin':
        nativesFile = lib["natives"]["osx"].replace("${arch}", arch)
    elif "linux" in lib["natives"] and platform.system() == "Linux":
        nativesFile = lib["natives"]["linux"].replace("${arch}", arch)
    else:
        return ""

    print(nativesFile)
    return nativesFile

def getClasspath(lib, gameDir):
    cp = []

    for i in lib["libraries"]:
        if not libraryCheck(i):
            continue
        libDomain, libName, libVersion = i["name"].split(":")
        jarPath = os.path.join(gameDir, "libraries", *
                               libDomain.split('.'), libName, libVersion)

        native = getNatives(i)
        jarFile = libName + "-" + libVersion + ".jar"
        if native != "":
            jarFile = libName + "-" + libVersion + "-" + native + ".jar"

        cp.append(os.path.join(jarPath, jarFile))

    cp.append(os.path.join(gameDir, "versions", lib["id"], f'{lib["id"]}.jar'))

    return os.pathsep.join(cp)

def getUUID(username):
    tempuuid = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{username}")
    data = tempuuid.json()
    return data["id"]

def inherit(data, gameDir):
    inherit_version = data["inheritsFrom"]
    with open(os.path.join(gameDir, "versions", inherit_version, inherit_version + ".json")) as f:
        new_data = json.load(f)
    for key, value in data.items():
        if isinstance(value, list) and isinstance(new_data.get(key, None), list):
            new_data[key] = value + new_data[key]
        elif isinstance(value, dict) and isinstance(new_data.get(key, None), dict):
            for a, b in value.items():
                if isinstance(b, list):
                    new_data[key][a] = new_data[key][a] + b
        else:
            new_data[key] = value
    return new_data

def authenticateEmail():
    email = input("Please enter your email: ")
    password = input("Please enter your password: ")
    
    payload = {
        "agent": {
            "name": "Minecraft",
            "version": 1
        },
        "username": email,
        "password": password,
        "clientToken": uuid.uuid4().hex
    }
    response = requests.post("https://authserver.mojang.com/authenticate", json=payload).json()

    auth = {"username": response["selectedProfile"]["name"], "uuid": response["selectedProfile"]["id"], "token": response["accessToken"], "clientToken": response["clientToken"]}
    with open("token.json", "w") as f:
        f.write(json.dumps(auth, indent=4))
    
    return auth

def printAndGetVersion(gameDir):
    directories = next(os.walk(gameDir + "versions"))[1]
    for i in directories:
        print(i)

    version = input("Please enter the version from above options: ")
    if version in directories:
        return version
    else:
        print("Not a valid version!")
        sys.exit()

def validateAndRefresh():
    try:
        with open("token.json", "r") as f:
            auth = json.load(f)
    except Exception as e:
        print(e)
        auth = authenticateEmail()
        return auth 

    payload = {
        "accessToken": auth["token"],
    }
    response = requests.post("https://authserver.mojang.com/validate", json=payload)
    
    if response.status_code == 204:
        return auth
    else:
        payload = {
            "accessToken": auth["token"],
            "clientToken": auth["clientToken"],
        }
        
    response = requests.post("https://authserver.mojang.com/refresh", json=payload).json()
    auth = {"username": response["selectedProfile"]["name"], "uuid": response["selectedProfile"]["id"], "token": response["accessToken"], "clientToken": response["clientToken"]}
    with open("token.json", "w") as f:
        f.write(json.dumps(auth, indent=4))
    
    return auth

def launch(version=None, auth=None, javaVersion=r"C:\Program Files\Java\jdk-16.0.1\bin\java.exe"):    
    auth = validateAndRefresh()

    username = auth["username"]
    accountuuid = auth["uuid"]
    accessToken = auth["token"]

    localuser = str(getpass.getuser())
    homeDir = f'C:/Users/{localuser}'
    gameDir = f'{homeDir}/AppData/Roaming/.minecraft/'

    if version == None:   
        version = printAndGetVersion(gameDir)
        
    natives = os.path.join(gameDir, 'versions', version, 'natives')
    
    clientJson = json.loads(Path(os.path.join(gameDir, 'versions', version, f'{version}.json')).read_text())

    if "inheritsFrom" in clientJson:
        clientJson = inherit(clientJson, gameDir)
        assetsVersion = clientJson["inheritsFrom"]
    else:
        assetsVersion = version
    if "forge" in version:
        tweakClass = "net.minecraftforge.fml.common.launcher.FMLTweaker"
        print("a")
    else:
        tweakClass = ""


    minecraftClass = clientJson['mainClass']
    versionType = clientJson['type']
    classPath = getClasspath(clientJson, gameDir)
    print(classPath)

    if tweakClass != "": # check if FML // Forge, as I have custom ClassPaths setup. I didn't make documentation on how to obtain these classpaths so DM me personally on discord if want help getting them! (bren#0069)
        sp.call([
            javaVersion,
            '-Djava.library.path=',
            rf"C:\Users\{localuser}\AppData\Roaming\.minecraft\bin\1.8natives"
            '-Dminecraft.launcher.brand=custom-launcher',
            '-Dminecraft.launcher.version=2.1',
            '-cp',
            rf"C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\net\minecraftforge\forge\1.8.9-11.15.1.2318-1.8.9\forge-1.8.9-11.15.1.2318-1.8.9.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\net\minecraft\launchwrapper\1.12\launchwrapper-1.12.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\ow2\asm\asm-all\5.0.3\asm-all-5.0.3.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\jline\jline\2.13\jline-2.13.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\typesafe\akka\akka-actor_2.11\2.3.3\akka-actor_2.11-2.3.3.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\typesafe\config\1.2.1\config-1.2.1.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\scala-lang\scala-actors-migration_2.11\1.1.0\scala-actors-migration_2.11-1.1.0.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\scala-lang\scala-compiler\2.11.1\scala-compiler-2.11.1.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\scala-lang\plugins\scala-continuations-library_2.11\1.0.2\scala-continuations-library_2.11-1.0.2.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\scala-lang\plugins\scala-continuations-plugin_2.11.1\1.0.2\scala-continuations-plugin_2.11.1-1.0.2.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\scala-lang\scala-library\2.11.1\scala-library-2.11.1.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\scala-lang\scala-parser-combinators_2.11\1.0.1\scala-parser-combinators_2.11-1.0.1.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\scala-lang\scala-reflect\2.11.1\scala-reflect-2.11.1.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\scala-lang\scala-swing_2.11\1.0.1\scala-swing_2.11-1.0.1.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\scala-lang\scala-xml_2.11\1.0.2\scala-xml_2.11-1.0.2.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\lzma\lzma\0.0.1\lzma-0.0.1.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\net\sf\jopt-simple\jopt-simple\4.6\jopt-simple-4.6.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\java3d\vecmath\1.5.2\vecmath-1.5.2.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\net\sf\trove4j\trove4j\3.0.3\trove4j-3.0.3.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\mojang\netty\1.6\netty-1.6.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\oshi-project\oshi-core\1.1\oshi-core-1.1.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\net\java\dev\jna\jna\3.4.0\jna-3.4.0.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\net\java\dev\jna\platform\3.4.0\platform-3.4.0.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\ibm\icu\icu4j-core-mojang\51.2\icu4j-core-mojang-51.2.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\paulscode\codecjorbis\20101023\codecjorbis-20101023.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\paulscode\codecwav\20101023\codecwav-20101023.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\paulscode\libraryjavasound\20101123\libraryjavasound-20101123.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\paulscode\librarylwjglopenal\20100824\librarylwjglopenal-20100824.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\paulscode\soundsystem\20120107\soundsystem-20120107.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\io\netty\netty-all\4.0.23.Final\netty-all-4.0.23.Final.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\google\guava\guava\17.0\guava-17.0.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\apache\commons\commons-lang3\3.3.2\commons-lang3-3.3.2.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\commons-io\commons-io\2.4\commons-io-2.4.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\commons-codec\commons-codec\1.9\commons-codec-1.9.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\net\java\jinput\jinput\2.0.5\jinput-2.0.5.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\net\java\jutils\jutils\1.0.0\jutils-1.0.0.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\google\code\gson\gson\2.2.4\gson-2.2.4.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\mojang\authlib\1.5.21\authlib-1.5.21.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\com\mojang\realms\1.7.59\realms-1.7.59.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\apache\commons\commons-compress\1.8.1\commons-compress-1.8.1.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\apache\httpcomponents\httpclient\4.3.3\httpclient-4.3.3.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\commons-logging\commons-logging\1.1.3\commons-logging-1.1.3.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\apache\httpcomponents\httpcore\4.3.2\httpcore-4.3.2.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\apache\logging\log4j\log4j-api\2.0-beta9\log4j-api-2.0-beta9.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\apache\logging\log4j\log4j-core\2.0-beta9\log4j-core-2.0-beta9.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\lwjgl\lwjgl\lwjgl\2.9.4-nightly-20150209\lwjgl-2.9.4-nightly-20150209.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\org\lwjgl\lwjgl\lwjgl_util\2.9.4-nightly-20150209\lwjgl_util-2.9.4-nightly-20150209.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\libraries\tv\twitch\twitch\6.5\twitch-6.5.jar;C:\Users\{localuser}\AppData\Roaming\.minecraft\versions\1.8.9\1.8.9.jar",
            "net.minecraft.launchwrapper.Launch",
            '--username',
            username,
            '--version',
            version,
            '--gameDir',
            gameDir,
            '--assetsDir',
            os.path.join(gameDir, 'assets'),
            '--assetIndex',
            assetsVersion,
            '--uuid',
            accountuuid,
            '--accessToken',
            accessToken,
            '--userType',
            'mojang',
            '--versionType',
            'release',
            '--tweakClass',
            tweakClass
        ])
    else: # this part should work for any other version of minecraft, like Fabric or Vanilla
        sp.call([
            javaVersion,
            f'-Djava.library.path={natives}',
            '-Dminecraft.launcher.brand=custom-launcher',
            '-Dminecraft.launcher.version=2.1',
            '-cp',
            classPath,
            minecraftClass,
            '--username',
            username,
            '--version',
            version,
            '--gameDir',
            gameDir,
            '--assetsDir',
            os.path.join(gameDir, 'assets'),
            '--assetIndex',
            assetsVersion,
            '--uuid',
            accountuuid,
            '--accessToken',
            accessToken,
            '--userType',
            'mojang',
            '--versionType',
            'release'
        ])

if __name__ == '__main__':
    launch()