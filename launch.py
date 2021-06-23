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

    auth = {'username': response['selectedProfile']["name"], "uuid": response['selectedProfile']['id'], 'token': response['accessToken'], "clientToken": response['clientToken']}
    with open("token.json", "w") as f:
        f.write(str(auth))
    
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
    except:
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
            'accessToken': auth["token"],
            'clientToken': auth["clientToken"],
        }
    response = requests.post("https://authserver.mojang.com/refresh", json=payload).json()
    auth = {'username': response['selectedProfile']["name"], "uuid": response['selectedProfile']['id'], 'token': response['accessToken'], "clientToken": response['clientToken']}
    with open("token.json", "w") as f:
        f.write(str(auth))
    
    return auth


def launch(version=None, auth=None):
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

    minecraftClass = clientJson['mainClass']
    versionType = clientJson['type']
    classPath = getClasspath(clientJson, gameDir)


    sp.call([
        'java',
        f'-Djava.library.path={natives}',
        '-Dminecraft.launcher.brand=custom-launcher',
        '-Dminecraft.launcher.version=2.1',
        '-cp',
        classPath,
        'net.fabricmc.loader.launch.knot.KnotClient',
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