import httplib2, sys, os, uuid, json, urllib, zipfile, textwrap
from xml.dom import minidom

class ATLDownloader:
    def __init__(self):
        self.h = httplib2.Http(".cache")
        self.user_agent = "Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.72 Safari/537.36 ATLauncher/3.1.23"
        self.__uuid = str(uuid.uuid1())

        #stuff for the downloading routine
        self.__browserdownloads = []
        self.__minecraftversion = ""
        self.__optionalModsToDownload = []

    def getMinecraftLogin(self, username, password):
        authRequest = json.dumps({
          "agent": {
              "name":"Minecraft",
              "version":10,
              },
           "username": username,
           "password": password,
           "clientToken": self.__uuid,
           "requestUser": True,
        })

        resp, content = self.h.request(
            uri="https://authserver.mojang.com/authenticate",
            method='POST',
            headers={'Content-Type': 'application/json; charset=UTF-8'},
            body=authRequest,
        )

        print content

        authResponse = json.loads(content)
        return str(authResponse["selectedProfile"]["name"]), \
               str(authResponse["accessToken"]), \
               str(authResponse["clientToken"]) # ist die UUID von oben

    def getAuthKey(self, username, accessToken, clientToken):
        print urllib.urlencode({"username" : username, "accessToken" : accessToken, "clientToken" : clientToken})

        resp, content = self.h.request(
            uri= "http://files.atlcdn.net/getauthkeynew.php",
            method='POST',
            headers= {"User-Agent": self.user_agent,
                      "Expires" : "0", "Pragma": "no-cache",
                      "Cache-Control": "no-store,max-age=0,no-cache",
                      "Content-type": "application/x-www-form-urlencoded",
                      },
            body =  urllib.urlencode({"username" : username,
                                      "accessToken" : accessToken,
                                      "clientToken" : clientToken})
        )

        print content
        keys = content.split('|')

        auth_key = keys[0] + "|" + keys[1]
        return auth_key

    def createHeader(self, authKey):
        return {"User-Agent": self.user_agent,
                "Auth-Key": authKey,
                "Expires" : "0", "Pragma": "no-cache",
                "Cache-Control": "no-store,max-age=0,no-cache"}

    def getModlist(self, headers, modname, version, safeToFile = False):
        configuri = "http://files.atlcdn.net/packs/" + modname + "/versions/" + version + "/Configs.xml"

        print "Downloading " + configuri

        resp_headers, configs_xml = self.h.request(
            uri= configuri,
            headers=headers,
        )

        if safeToFile:
            output = open("Config.xml" ,'wb')
            output.write(configs_xml)
            output.close()

        return minidom.parseString(configs_xml)

    def downloadMods(self, headers, modlist):

        mods = modlist.getElementsByTagName('mod')

        self.__prepareOptionalMods(mods)

        self.__minecraftversion = modlist.getElementsByTagName("minecraft")[0].childNodes[0].data
        print "Downloading ~"+str(mods.length)+" mods..."

        if not os.path.exists("mods/") or not os.path.exists("mods/1.6.4/"):
            os.makedirs("mods/1.6.4/")

        self.__browserdownloads = []

        for mod in mods:
            self.__downloadMod(mod)

        if len(self.__browserdownloads) > 0:
            print "The following mods need to be downloaded manually:"
            for mod in self.__browserdownloads:
                print "["+ mod["name"] + "] " + mod["url"]

    def __prepareOptionalMods(self, modlist):
        """
            To create a list of mods we download later on. This is used to handle the dependencies.
        """
        print "Preparing optional mods"
        self.__optionalModsToDownload = []
        for mod in modlist:

            if mod.hasAttribute('server') and mod.attributes['server'].value == "no":
                continue

            if mod.hasAttribute('optional') and mod.attributes['optional'].value == "yes":

                modname = mod.attributes['name'].value
                print "..." + modname + " [" +mod.attributes['version'].value +  "]"

                if mod.hasAttribute('recommended') and mod.attributes['recommended'].value == 'yes':
                    print "......it is recommended"

                print "......the description sais: " + mod.attributes['description'].value

                answer = raw_input("......download it? (Y/N): ")
                if answer not in ['Y', 'y', ]:
                    continue
                print "......okai, downloading"

                self.__optionalModsToDownload.append(modname)
                if mod.hasAttribute('depends'):
                    print "......and it's dependency: " + mod.attributes['depends'].value
                    self.__optionalModsToDownload.append(mod.attributes['depends'].value)

    def __downloadMod(self, mod):
        modname = mod.attributes['name'].value
        print "..." + modname

        if mod.hasAttribute('server') and mod.attributes['server'].value == "no":
            return

        if mod.hasAttribute('optional') and mod.attributes['optional'].value == "yes":
            print "......is optional"
            if modname not in self.__optionalModsToDownload:
                print "......not selected"
                return
            print "......but has been selected"

        #attach the urls of those adf.ly links to a list for later
        if mod.attributes['download'].value == 'browser':
            print "......is a manual download, saving link"
            self.__browserdownloads.append({"name":mod.attributes['name'].value,
                                            "url":mod.attributes['url'].value})
            return

        resp_headers, mod_file = self.h.request(
            uri= "http://files.atlcdn.net/" + mod.attributes['url'].value,
            headers=headers,
        )

        #different folders for different types
        modtype = mod.attributes["type"].value
        subfolder = ""
        if modtype == "forge":
            subfolder = ""
        elif modtype == "mods":
            subfolder = "mods/"
        elif modtype == "resourcepack":
            subfolder = "resourcepacks/"
        elif modtype == "dependency":
            subfolder = "mods/" + self.__minecraftversion + "/"

        file = subfolder + mod.attributes['file'].value
        output = open(file ,'wb')
        output.write(mod_file)
        output.close()

        if modtype == "extract":
            self.__extractMod(mod, file)

    def __extractMod(self, mod, file):
        print "......this needs to be extracted, extracting..."
        zfile = zipfile.ZipFile(file)
        subfolder = "mods/" if mod.attributes["extractto"].value == "mods" else ""
        zfile.extractall(subfolder)
        zfile.close()
        os.remove(file)
        print "......done."

    def downloadLibraries(self, headers, modlist):
        libraries = modlist.getElementsByTagName('library')
        print "Downloading ~"+str(libraries.length)+" libraries..."

        for lib in libraries:
            print "..." + lib.attributes['file'].value

            if not lib.hasAttribute('server'):
                print "......no server attribute, ignoring"
                continue

            path = "libraries/" + lib.attributes["server"].value

            #make folders
            folders = path[:path.rfind("/")+1]
            if not os.path.exists(folders):
                os.makedirs(folders)

            #download and safe file
            resp_headers, lib_file = self.h.request(
                uri= "http://files.atlcdn.net/" + lib.attributes['url'].value,
                headers=headers
            )
            output = open(path ,'wb')
            output.write(lib_file)
            output.close()

    def downloadConfig(self, headers, modname, version):
        configuri = "http://files.atlcdn.net/packs/" + modname + "/versions/" + version + "/Configs.zip"
        print "Downloading " + configuri

        resp_headers, configs_zip = self.h.request(
            uri= configuri,
            headers=headers,
        )

        output = open("Configs.zip" ,'wb')
        output.write(configs_zip)
        output.close()

        zfile = zipfile.ZipFile("Configs.zip")
        zfile.extractall("")
        zfile.close()
        os.remove("Configs.zip")

    def downloadMinecraftServer(self, headers):
        name = "minecraft_server." + self.__minecraftversion + ".jar"
        uri = "http://s3.amazonaws.com/Minecraft.Download/versions/"+self.__minecraftversion+"/"+name
        print "Downloading " + uri

        resp_headers, server = self.h.request(
            uri= uri,
            headers=headers,
        )

        output = open(name ,'wb')
        output.write(server)
        output.close()

__author__ = 'Worfox'

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
'''This downloads modpacks from the ATLauncher.
  This has ZERO error handling, expect strange exceptions and errors if things have changed.

  If if this is the first time you are using this, here are some hints:
  * There will be a subdirectory created for that modpackname
  * Use the -l or -login argument if you don't know what an authKey is

  Some Modpacks are:
  ResonantRise          2.8.3.4-RR-MAIN
  YogscastCompletePack  2.8.3.4-RR-YOGS
  SkyFactory            1.2
'''
        ),
        epilog=textwrap.dedent(
'''usage examples:
  %(prog)s -l MCplayer123 MyPassword ResonantRise 2.8.3.4-RR-MAIN
  %(prog)s -l super@duper.com Password SkyFactory 1.2
  %(prog)s -k 64567247h456dzh5356jw5kdfh933458|568536736 YogscastCompletePack 2.8.3.4-RR-YOGS
'''),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-l", "--login", nargs=2, help="Your Minecraft.com username and password", metavar=("Username","Password"))
    group.add_argument("-k", "--authKey", help="The authkey you get after logging in.")
    parser.add_argument("modpackname", help="The exact name of the modpack you want do download")
    parser.add_argument("modpackversion", help="The version of the modpack")
    args = parser.parse_args()

    #change working directory to modpack name
    if not os.path.exists(args.modpackname):
        os.makedirs(args.modpackname)
    os.chdir(args.modpackname)

    atldl = ATLDownloader()

    if args.login is not None:
        username, accessToken, clientToken = atldl.getMinecraftLogin(args.login[0], args.login[1])
        authKey = atldl.getAuthKey(username, accessToken, clientToken)
    else:
        authKey = args.authKey

    headers = atldl.createHeader(authKey)
    modlist = atldl.getModlist(headers, args.modpackname, args.modpackversion, safeToFile=True)

    atldl.downloadLibraries(headers, modlist)
    atldl.downloadMods(headers, modlist)
    atldl.downloadConfig(headers, args.modpackname, args.modpackversion)
    atldl.downloadMinecraftServer(headers)

    print "Done!"
    if args.authKey is None:
        print "Use this authKey (--authKey <key>) to skip the minecraft login next time: " + authKey

