# coding=utf-8
'''
Created on 22/01/2014

#Author: Adastra.
#twitter: @jdaanial

deepWebDirBruterPlugin.py

deepWebDirBruterPlugin is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

deepWebDirBruterPlugin is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Tortazo; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
'''

from core.tortazo.pluginManagement.BasePlugin import BasePlugin
from requests.exceptions import ConnectionError
from requests.exceptions import Timeout

class deepWebDirBruterPlugin(BasePlugin):

    def __init__(self, torNodes=[]):
        BasePlugin.__init__(self, torNodes, 'deepWebDirBruterPlugin')
        self.setPluginDetails('deepWebDirBruterPlugin', 'Find directories in the specified onion url.', '1.0', 'Adastra: @jdaanial')
        if len(torNodes) > 0:
            self.info("[*] deepWebDirBruterPlugin Initialized!")
        self.bruteForceData = {}
        for torNode in self.torNodes:
            openPorts = []
            for port in torNode.openPorts:
                openPorts.append(port.port)
                if len(openPorts) > 0:
                    self.bruteForceData[torNode.host] = openPorts
        self.separator = ":"

    def __del__(self):
        if len(self.torNodes) > 0:
            self.debug("[*] deepWebDirBruterPlugin Destroyed!")

    def setDictSeparator(self, separator):
        print "[+] Setting separator '%s' for dictionary files. Every line en the file must contain <user><separator><passwd>" %(separator)
        self.separator = separator


        print "[+] Starting DirBruter plugin against %s ... This could take some time. Be patient."

    def dirBruterOnRelay(self, site, dictFile='', proxy=False):
        if proxy:
            self.serviceConnector.performHTTPConnectionHiddenService(site)
        else:
            print "[+] Trying to find directories in the webserver %s " %(site)
            print "[+] Verifying if the path %s is reachable ... " %(site)
            try:
                initialResponse = self.serviceConnector.performHTTPConnection(site)
                if initialResponse.status_code in range(400, 499) or initialResponse.status_code in range(500, 599):
                    print "[-] The web server responded with an HTTP error Code ... HTTP %s " %(str(initialResponse.status_code))
                else:
                    if dictFile == '':
                        print "[+] No specified 'dictFile'. Using FuzzDB Project to execute the attack."
                        print "[+] Starting the attack using the FuzzDB Files ... This could take some time."
                        dirList = self.fuzzDBReader.getDirListFromFuzzDB()
                        for dir in dirList:
                            response= self.serviceConnector.performHTTPConnection(site+dir)
                            if response.status_code in range(200,299):
                                print "[+] Resource found!  %s  " %(dir)
                    else:
                        print "[+] Reading dict. file %s using the separator '%s' ... " %(dictFile,self.separator)



            except ConnectionError:
                print "[-] Seems that the webserver in path %s is not reachable. Aborting the attack..." %(site)
            except Timeout:
                pass



    def dirBruterOnAllRelays(self, port=80, dictFile=''):
        for relay in self.bruteForceData:
            self.dirBruterOnRelay("http://"+relay, proxy=False)

    def dirBruterOnHiddenService(self):
        self.dirBruterOnRelay(relay=relay, port=port, dictFile=dictFile, proxy=False)
