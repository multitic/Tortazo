# coding=utf-8
'''
Created on 22/01/2014

#Author: Adastra.
#twitter: @jdaanial

Tortazo.py

Tortazo is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

Tortazo is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Tortazo; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
'''

import os.path
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))


from core.tortazo.Discovery import Discovery
from core.tortazo.BotNet import BotNet
from core.tortazo.Reporting import Reporting
from core.tortazo.databaseManagement.TortazoServerDB import  TortazoSQLiteDB, TortazoPostgreSQL, TortazoMySQL
from core.tortazo.OnionRepository import  RepositoryGenerator
from core.tortazo.utils.ServiceConnector import ServiceConnector
from config import config as tortazoConfiguration
import Queue
from stem.util import term
import stem.process
import logging as log
from plumbum import cli
from time import gmtime, strftime
from distutils.util import strtobool
import string
import random
from pyfiglet import Figlet
import time
from core.tortazo.exceptions.PluginException import PluginException

#
#  ████████╗ ██████╗ ██████╗ ████████╗ █████╗ ███████╗ ██████╗ 
#  ╚══██╔══╝██╔═══██╗██╔══██╗╚══██╔══╝██╔══██╗╚══███╔╝██╔═══██╗
#     ██║   ██║   ██║██████╔╝   ██║   ███████║  ███╔╝ ██║   ██║
#     ██║   ██║   ██║██╔══██╗   ██║   ██╔══██║ ███╔╝  ██║   ██║
#     ██║   ╚██████╔╝██║  ██║   ██║   ██║  ██║███████╗╚██████╔╝
#     ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝ ╚═════╝ 
#                                                              

#
#	Attack exit nodes of the TOR Network.
#	Author: Adastra.
#	http://thehackerway.com
#
#   TODO IN V1.1:
#   - Report issues to the administrator of the exitnode.
#   - Upload and execute files to the compromised machines using SFTP and FTP.
#   - Check subterfuge: http://code.google.com/p/subterfuge/
#   - Check what do bannergrab:  http://sourceforge.net/projects/bannergrab/
#   - GeoLocation, for example using: http://www.melissadata.com/lookups/iplocation.asp?ipaddress=46.17.138.212
#   - Use PyInstaller to generate an executable for Linux and Windows.
#   - Plugin Arguments. Socks Settings, Start TOR Instance, etc.
#   - Develop unit tests using Python unittest.
#   - Plugin for Metasploit Framework.
#   - Plugin for Nikto.
#   - Plugin for NeXpose.


#    TODO FIXES:
#    - Report generated by Jinja2, align the column of ports in Nmap report.
#    - More tests about the W3AF and Nessus plugins.


class Cli(cli.Application):
    '''
    Command-Line options received.
    '''
    PROGNAME = "TORTAZO"
    AUTHOR = "Adastra"
    VERSION = "1.1"
    DESCRIPTION = "Tortazo is used to audit and attack hidden services and relays in TOR"
    verbose = cli.Flag(["-v", '--verbose'], help="Verbose Mode.")
    useMirror = cli.Flag(["-d", '--use-mirrors'], help="Use the mirror directories of TOR. This will help to not overwhelm the official directories")
    useShodan = cli.Flag(["-s", '--use-shodan'], help="Use ShodanHQ Service. (Specify -k/--shodan-key to set up the file where's stored your shodan key.)")
    useCircuitExitNodes = cli.Flag(["-c", "--use-circuit-nodes"], help="Use the exit nodes selected for a local instance of TOR.")
    openShell = cli.Flag(["-o", "--open-shell"], excludes=["--mode"], requires=["--zombie-mode"],  help="Open a shell on the specified host.")
    useDatabase = cli.Flag(["-D", '--use-database'], help="Tortazo will store the last results from the scanning process in a database. If you use this flag, Tortazo will omit the scan and just will try use the data stored from the last execution.")
    cleanDatabase = cli.Flag(["-C", '--clean-database'], help="Tortazo will delete all records stored in database when finished executing. This option will delete every record stored, included the data from previous scans.")
    listPlugins = cli.Flag(["-L", '--list-plugins'], help="List of plugins loaded.")
    useLocalTorInstance = cli.Flag(["-U", '--use-localinstance'], help="Use a local TOR instance started with the option -T/--tor-localinstance (Socks Proxy included) to execute requests from the plugins loaded. By default, if you don't start a TOR local instance and don't specify this option, the settings defined in 'config.py' will be used to perform requests to hidden services.")

    exitNodesToAttack = 10 #Number of default exit-nodes to filter from the Server Descriptor file.
    shodanKey = None #ShodanKey file.
    scanPorts = "21,22,23,53,69,80,88,110,139,143,161,162,389,443,445,1079,1080,1433,3306,5432,8080,9050,9051,5800" #Default ports used to scan with nmap.
    scanArguments = None #Scan Arguments passed to nmap.
    exitNodeFingerprint = None #Fingerprint of the exit-node to attack.
    queue = Queue.Queue() #Queue with the host/open-port found in the scanning.
    controllerPort = '9151'
    zombieMode = None
    mode = None
    runCommand = None
    pluginManagement = None
    pluginArguments =  None
    torLocalInstance = None
    scanIdentifier = None
    activateOnionRepositoryMode = None
    workerThreads = 10
    onionRepositoryMode = ""
    validchars ='234567' + string.lowercase

    socksHost = None
    socksPort = None

    @cli.switch(["-n", "--servers-to-attack"], int, help="Number of TOR exit-nodes to attack. If this switch is used with --use-database, will recover information stored from the last 'n' scans. Default = 10")
    def servers_to_attack(self, exitNodesToAttack):
        '''
        Number of "exit-nodes" to attack received from command-line
        '''
        self.exitNodesToAttack = exitNodesToAttack

    @cli.switch(["-m", "--mode"], cli.Set("windows", "linux", "darwin", "freebsd", "openbsd", "bitrig","netbsd", case_sensitive=False),  excludes=["--zombie-mode"] , help="Filter the platform of exit-nodes to attack.")
    def server_mode(self, mode):
        '''
        Server Mode: Search for Windows or Linux machines.
        '''
        self.mode = mode

    @cli.switch(["-k", "--shodan-key"], str, help="Development Key to use Shodan API.", requires=["--use-shodan"])
    def shodan_key(self, shodanKey):
        '''
        This option is used to specify the file where the shodan development key is stored
        '''
        self.shodanKey = shodanKey

    @cli.switch(["-l", "--list-ports"], str, help="Comma-separated List of ports to scan with Nmap. Don't use spaces")
    def list_ports(self, scanPorts):
        '''
        List of ports used to perform the nmap scan.
        '''
        self.scanPorts = scanPorts

    @cli.switch(["-a", "--scan-arguments"], str, help='Arguments to Nmap. Use "" to specify the arguments. For example: "-sSV -A -Pn"')
    def scan_arguments(self, scanArguments):
        '''
        Arguments used to perform the nmap scan.
        '''
        self.scanArguments = scanArguments

    @cli.switch(["-e", "--exit-node-fingerprint"], str, help="ExitNode's Fingerprint to attack.")
    def exitNode_Fingerprint(self, exitNodeFingerprint):
        '''
        If we want to perform a single attack against an known "exit-node", We can specify the fingerprint of the exit-node to perform the attack.
        '''
        self.exitNodeFingerprint = exitNodeFingerprint

    @cli.switch(["-i", "--controller-port"], str, help="Controller's port of the local instance of TOR. (Default=9151)", requires=["--use-circuit-nodes"])
    def controller_port(self, controllerPort):
        '''
        Controller's Port. Default=9151
        '''
        self.controllerPort = controllerPort

    @cli.switch(["-z", "--zombie-mode"], str, help="This option reads the tortazo_botnet.bot file generated from previous successful attacks. With this option you can select the Nicknames that will be excluded. (Nicknames included in the tortazo_botnet.bot). For instance, '-z Nickname1,Nickname2' or '-z all' to include all nicknames.")
    def zombie_mode(self, zombieMode):
        '''
        Zombie mode to execute commands across the compromised hosts.
        '''
        if zombieMode == None:
            self.zombieMode = ""
        self.zombieMode = zombieMode

    @cli.switch(["-r", "--run-command"], str, excludes=["--mode"], requires=["--zombie-mode"],  help='Execute a command across the hosts of the botnet. Requieres the -z/--zombie-mode. example: --run-command "uname -a; uptime" ')
    def run_command(self, runCommand):
        '''
        Command to execute across the compromised hosts.
        '''
        self.runCommand = runCommand

    @cli.switch(["-P", "--use-plugin"], str, help='Execute a plugin. To see the available plugins, execute Tortazo with switch -L / --list-plugins')
    def plugin_management(self, pluginManagement):
        '''
        Plugin Management.
        '''
        self.pluginManagement = pluginManagement

    @cli.switch(["-A", "--plugin-arguments"], str, requires=["--use-plugin"],  help='Args to execute the specified plugin with the switch -P / --use-plugin. List of key/value pairs separated by colon. Example= nessusHost=127.0.0.1,nessusPort=8843,nessusUser=adastra,nessusPassword=adastra')
    def plugin_arguments(self, pluginArguments):
        '''
        Plugin Arguments.
        '''
        self.pluginArguments = pluginArguments



    @cli.switch(["-T", "--tor-localinstance"], str, help='Start a new local TOR instance with the "torrc" file specified. DO NOT RUN TORTAZO WITH THIS OPTION AS ROOT!')
    def tor_localinstance(self, torLocalInstance):
        '''
        TOR Local Instance.
        '''
        self.torLocalInstance = torLocalInstance

    @cli.switch(["-S", "--scan-identifier"], int, requires=["--use-database"],  help="scan identifier in the Scan table. Tortazo will use the relays related with the scan identifier specified with this option.")
    def scan_identifier(self, scanIdentifier):
        '''
        Scan Identifier. Tortazo will use the relays associated with this scan. (Relation between the Scan and TorNodeData tables.)
        '''
        self.scanIdentifier = scanIdentifier

    @cli.switch(["-O", "--onionpartial-address"], str, help="Partial address of a hidden service. Used in Onion repository mode.")
    def onionRepository_mode(self, onionRepositoryMode):
        '''
        Generator Threads. Number of threads used by the generator of onion addresses.
        '''
        self.onionRepositoryMode = onionRepositoryMode

    @cli.switch(["-R", "--onion-repository"], cli.Set("ssh", "ftp", "http", "onionup", case_sensitive=False), help="Activate the Onion Repository mode and try to find hidden services in the TOR deep web.")
    def activateOnionRepository_Mode(self, activateOnionRepositoryMode):
        '''
        Onion repository mode.
        '''
        self.activateOnionRepositoryMode = activateOnionRepositoryMode

    @cli.switch(["-W", "--workers-repository"], int, requires=["--onion-repository"], help="Number of threads used to process the ONION addresses generated.")
    def workers_repository(self, workers_repository):
        '''
        Worker Threads for processing the ONION addresses generated.
        '''
        self.workerThreads = workers_repository




    @cli.switch(["-V", "--validchars-repository"], str, help="Valid characters to use in the generation process of onion addresses. Default: All characters between a-z and digits between 2-7")
    def validchars_repository(self, validchars_repository):
        '''
        Valid characters to use in the generation process of onion addresses.
        '''
        self.validchars = validchars_repository

    def logsTorInstance(self, log):
        '''
        Shows the Logs for the TOR startup.
        '''
        self.logger.debug(term.format(log, term.Color.GREEN))

    def __killTorProcess(self):
        #If TOR process has been started, it should be stopped.
        if hasattr(self, 'torProcess') and self.torProcess is not None:
            self.logger.info(term.format("[+] Killing TOR process with PID %s " %(self.torProcess.pid), term.Color.YELLOW))
            self.torProcess.kill()
        self.logger.info((term.format("[+] Process finished at "+ strftime("%Y-%m-%d %H:%M:%S", gmtime()), term.Color.YELLOW)))


    def main(self):
        '''
        Initialization of logger system and banner ascii.
        http://www.figlet.org/examples.html
        '''
        fonts = ['slant','doom','avatar', 'barbwire', 'big', 'bigchief', 'binary', 'calgphy2', 'chunky', 'colossal', 'computer','cosmic','cosmike','cyberlarge','digital','doh','dotmatrix',
                 'drpepper', 'eftitalic','eftiwater','epic','gothic','isometric1','invita', 'isometric2','isometric3', 'isometric4','larry3d', 'lean','linux','madrid','mini','ntgreek', 'ogre',
                 'poison','puffy','roman','rounded','runyc','script','shadow','slscript','small','speed','standard','starwars','straight','twopoint','univers','weird']
        bannerTortazo = Figlet(font=random.choice(fonts))
        print bannerTortazo.renderText('Tortazo v %s.%s' %(tortazoConfiguration.tortazo_majorversion,tortazoConfiguration.tortazo_minorversion) )

        bannerAuthor = Figlet(font='digital')
        print bannerAuthor.renderText('By Adastra ' )
        print bannerAuthor.renderText('@jdaanial \n' )

        self.logger = log
        self.exitNodes = []
        if tortazoConfiguration.dbPostgres:
            self.database = TortazoPostgreSQL()
        elif tortazoConfiguration.dbMySQL:
            self.database = TortazoMySQL()
        else:
            self.database = TortazoSQLiteDB()

        if self.verbose:
            self.logger.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
            self.logger.debug(term.format("[+] Verbose mode activated.", term.Color.GREEN))
        self.logger.info(term.format("[+] Process started at " + strftime("%Y-%m-%d %H:%M:%S", gmtime()), term.Color.YELLOW))

        if self.cleanDatabase:
            self.logger.info(term.format("[+] Cleaning database... Deleting all records.", term.Color.YELLOW))
            self.database.initDatabase()
            self.database.cleanDatabaseState()

        if self.listPlugins:
            print "[*] Plugins list... "
            import pluginsDeployed
            for plugin in pluginsDeployed.plugins.keys():
                completeModulePath = pluginsDeployed.plugins.get(plugin)
                pluginModule = completeModulePath[:completeModulePath.rfind(".")]
                module = __import__(pluginModule)
                components = completeModulePath.split('.')
                for comp in components[1:]:
                    module = getattr(module, comp)
                inst = module([])
                print "Plugin package: %s" %(completeModulePath)
                print "Plugin Name: %s" %(inst.name)
                print "Plugin Description: %s" %(inst.desc)
                print "Plugin Version: %s" %(inst.version)
                print "Plugin Author: %s" %(inst.author)
                print "Plugin Arguments Available: %s" %(inst.pluginConfigs.keys())
                print "\n"
            return

        if self.torLocalInstance:
            if os.path.exists(self.torLocalInstance) and os.path.isfile(self.torLocalInstance):
                torrcFile = open(self.torLocalInstance,'r')
                torConfig = {}
                import pwd

                if pwd.getpwuid(os.getuid()).pw_uid != 0:
                    #Running TOR as non-root user. GOOD!
                    for line in torrcFile:
                        if line.startswith("#", 0, len(line)) is False and len(line.split()) > 0:
                            torOptionName = line.split()[0]
                            if len(line.split()) > 1:
                                torOptionValue = line[len(torOptionName)+1 : ]
                                torConfig[torOptionName] = torOptionValue
                    try:
                        self.logger.info(term.format("[+] Starting TOR Local instance with the following options: ", term.Color.YELLOW))
                        for config in torConfig.keys():
                            self.logger.info(term.format("[+] Config: %s value: %s " %(config, torConfig[config]), term.Color.YELLOW))
                        self.torProcess = stem.process.launch_tor_with_config(config = torConfig, tor_cmd = tortazoConfiguration.torExecutablePath, init_msg_handler=self.logsTorInstance)
                        time.sleep(5)
                        if self.torProcess > 0:
                            #If SocksListenAddress or SocksPort properties are empty but the process has been started, the socks proxy will use the default values.
                            self.logger.debug(term.format("[+] TOR Process created. PID %s " %(self.torProcess.pid),  term.Color.GREEN))
                            if torConfig.has_key('SocksListenAddress'):
                                self.socksHost = torConfig['SocksListenAddress']
                            else:
                                self.socksHost = '127.0.0.1'
                            if torConfig.has_key('SocksPort'):
                                self.socksPort = torConfig['SocksPort']
                            else:
                                #Starting TOR from the command "tor". The default Socks port in that case is '9050'. If you run tor with tor bundle, the default socks port is '9150'
                                self.socksPort = '9050'
                    except OSError, ose:
                        print sys.exc_info()
                        #OSError: Stem exception raised. Tipically, caused because the "tor" command is not in the path.
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        self.logger.warn(term.format("Exception raised during the startup of TOR Local instance.... "+str(ose), term.Color.RED))
                        self.logger.warn(term.format("Details Below: \n", term.Color.RED))
                        self.logger.warn(term.format("Type: %s " %(str(exc_type)), term.Color.RED))
                        self.logger.warn(term.format("Value: %s " %(str(exc_value)), term.Color.RED))
                        self.logger.warn(term.format("Traceback: %s " %(str(exc_traceback)), term.Color.RED))
                else:
                    self.logger.warn(term.format("You cannot run TOR as root user! Please, use an account with limited privileges ", term.Color.RED))
                    return

            else:
                self.logger.warn(term.format("The specified torrc file is not valid: %s " %(str(self.torLocalInstance)), term.Color.RED))

        if self.activateOnionRepositoryMode != None:
            #Tortazo should start a process and the goes to sleep. In this mode should not be other actions to be performed.
            #This switch will invalidate the other switches, just repository mode should be started.
            # Setup and start the simulation
            try:
                serviceConnector = ServiceConnector(self)
                self.logger.info(term.format("[+] Entering in Onion Repository Mode. This process could take a lot of time depending what you know of the hidden service to discover...", term.Color.YELLOW))
                if tortazoConfiguration.loadKnownOnionSites:
                    self.logger.info(term.format("[+] Reading the file of known hidden services located in 'db/knwonOnionSites.txt'. Tortazo will try to feed the local database with that information. If you want to avoid this behavior, set to False the property: 'loadKnownOnionSites' in the 'config/config.py' configuration file ...", term.Color.YELLOW))
                if self.onionRepositoryMode.lower() == 'random':
                    self.logger.info(term.format("[+] Random address generator selected ...", term.Color.YELLOW))
                else:
                    self.logger.info(term.format("[+] Incremental address generator selected ...", term.Color.YELLOW))
                    self.onionRepositoryMode = (self.onionRepositoryMode.replace('http://', '')).replace('.onion', '')
                    if len(self.onionRepositoryMode) == 0:
                        self.logger.warn(term.format("[+] Consider to use the switches -O / --onionpartial-address or -V / --validchars-repository to filter the results. ", term.Color.YELLOW))
                    if len(self.onionRepositoryMode) <= 10:
                        self.logger.warn(term.format("[+] You've entered an address with 10 or less characters [just %s chars]. The number of combinations will be very huge. You'll need a considerable process capacity in this machine and let run this process for hours, days or even weeks! If you're sure, let this process run" %(str(len(self.onionRepositoryMode))), term.Color.YELLOW))
                        sys.stdout.write('%s [y/n]\n' %('Are you sure?'))
                        while True:
                            try:
                                input = raw_input
                                if strtobool(input().lower()) == True:
                                    break
                                else:
                                    return
                            except NameError:
                                pass
                            except ValueError:
                                sys.stdout.write('Please respond with \'y\' or \'n\'.\n')
                if hasattr(self, "socksHost") and hasattr(self, "socksPort"):
                    if self.socksPort is not None and self.socksPort.isdigit():
                        serviceConnector.setSocksProxySettings(self.socksHost, int(self.socksPort))
                self.logger.info(term.format("[+] Starting the Onion repository mode against "+self.activateOnionRepositoryMode+" services...  " + strftime("%Y-%m-%d %H:%M:%S", gmtime()), term.Color.YELLOW))
                repository =  RepositoryGenerator(self.validchars, serviceConnector, self.database, self.onionRepositoryMode, self.workerThreads)
                repository.startGenerator(tortazoConfiguration.loadKnownOnionSites, self.activateOnionRepositoryMode)
                self.logger.info(term.format("[+] Onion repository finished...  " + strftime("%Y-%m-%d %H:%M:%S", gmtime()), term.Color.YELLOW))

            except KeyboardInterrupt:
                print "Interrupted!"
            except StandardError as standardExcept:
                self.logger.warn((term.format(standardExcept.message, term.Color.RED)))

            self.__killTorProcess()
            return
            #repository = RepositoryGenerator('',self.generatorThreads,self.workerThreads)
            #repository.startGenerator()
            #return


        if self.zombieMode is None and self.useDatabase is False and self.mode is None:
            self.logger.warn(term.format("Specify the execution mode. You should use Info Gathering (-m), Botnet Mode (-z) or Database Mode (-D). Type '--help' to see the available options. ", term.Color.RED))
            return

        #self.loadAndExecute(self,"simplePlugin:simplePrinter")
        '''
            List and Scan the exit nodes. The function will return an dictionary with the exitnodes found and the open ports.
            THIS PROCESS IS VERY SLOW AND SOMETIMES THE CONNECTION WITH THE DIRECTORY AUTHORITIES IS NOT AVAILABLE.
        '''
        if self.zombieMode:
            '''
            In zombie mode, The program should read the file named "tortazo_botnet.bot".
            In that file, every line have this format: host:user:password:nickname
            Extract every host and then, create a list of bots.
            '''
            botnet = BotNet(self)
            botnet.start()


        else:
            discovery = Discovery(self, self.database)

            if self.useDatabase:
                #There's a previous scan stored in database. We'll use that information!
                if self.scanIdentifier is None:
                    self.logger.info(term.format("[+] Getting the last %s scans executed from database..."  %(self.exitNodesToAttack),  term.Color.YELLOW))
                    self.logger.debug(term.format("[+] Use -n/--servers-to-attack option to include more or less records from the scans recorded in database.",  term.Color.GREEN))
                    self.exitNodes = self.database.searchExitNodes(self.exitNodesToAttack, None)
                else:
                    self.logger.info(term.format("[+] Getting the relays for the scan %d ..."  %(self.scanIdentifier),  term.Color.YELLOW))
                    self.exitNodes = self.database.searchExitNodes(self.exitNodesToAttack, self.scanIdentifier)

                if len(self.exitNodes) > 0:
                    self.logger.info(term.format("[+] Done!" , term.Color.YELLOW))
                else:
                    if self.scanIdentifier is None:
                        self.logger.info(term.format("[+] No records found... You should execute an initial scan." , term.Color.YELLOW))
                        self.logger.warn(term.format("[-] You've chosen to use the database records, however the database tables are empty because you have not run an initial scan." , term.Color.RED))
                    else:
                        self.logger.warn(term.format("[+] No records found with the scan identifier specified, check the database..." , term.Color.RED))
                    return
            else:
                if self.useCircuitExitNodes:
                    #Try to use a local instance of TOR to get information about the relays in the server descriptors.
                    self.exitNodes = discovery.listCircuitExitNodes()
                elif self.mode:
                    #Try to connect with the TOR directories to get information about the relays in the server descriptors.
                    self.exitNodes = discovery.listAuthorityExitNodes() #Returns a list of TorNodeData objects

            if self.exitNodes is not None and len(self.exitNodes) > 0:
                reporter = Reporting(self)
                reporter.generateNmapReport(self.exitNodes, tortazoConfiguration.NmapOutputFile)
                self.shodanHosts = []
                for torNode in self.exitNodes:
                    if self.useShodan == True:
                        #Using Shodan to search information about this machine in shodan database.
                        self.logger.info(term.format("[+] Shodan Activated. About to read the Development Key. ", term.Color.YELLOW))
                        if self.shodanKey == None:
                            #If the key is None, we can't use shodan.
                            self.logger.warn(term.format("[-] Shodan Key's File has not been specified. We can't use shodan without a valid key", term.Color.RED))
                        else:
                            #Read the shodan key and create the Shodan object.
                            try:
                                shodanKeyString = open(self.shodanKey).readline().rstrip('\n')
                                shodanHost = discovery.shodanSearchByHost(shodanKeyString, torNode.host)
                                self.shodanHosts.append(shodanHost)
                            except IOError, ioerr:
                                self.logger.warn(term.format("[-] Shodan's key File: %s not Found." %(self.shodanKey), term.Color.RED))

                if len(self.shodanHosts) > 0:
                    reporter.generateShodanReport(self.shodanHosts, tortazoConfiguration.ShodanOutputFile)

                #Check if there's any plugin to execute!
                if self.pluginManagement != None:
                    self.loadAndExecute(self.pluginManagement, self.exitNodes, self.pluginArguments)

        #If TOR process has been started, it should be stopped.
        self.__killTorProcess()

    def loadAndExecute(self, listPlugins, torNodesFound, pluginArguments=None):
        if listPlugins is None:
            self.logger.warn((term.format("[-] You should specify a plugin with the option -P/--use-plugin", term.Color.YELLOW)))
            return
        try:
            pluginArgs = {}
            if pluginArguments != None:
                arguments = pluginArguments.split(',')
                for argument in arguments:
                    key, value = argument.split('=')
                    print key, value
                    pluginArgs[key] = value

            import pluginsDeployed
            self.logger.debug((term.format("[+] Loading plugin...", term.Color.GREEN)))

            if pluginsDeployed.plugins.__contains__(listPlugins):
                completeModulePath = pluginsDeployed.plugins.get(listPlugins)
                pluginModule = completeModulePath[:completeModulePath.rfind(".")]
                module = __import__(pluginModule)
                components = completeModulePath.split('.')
                for comp in components[1:]:
                    module = getattr(module, comp)
                try:
                    if self.socksHost is not None and self.socksPort is not None and self.useLocalTorInstance:
                        self.logger.info((term.format("[+] You've started a TOR local instance and specified the -U/--use-localinstance option. The plugin loaded will use the following options to connect with TOR and Hidden Services in the deep web: " , term.Color.YELLOW)))
                        self.logger.info((term.format("[+] Host=%s , Port=%s" %(self.socksHost, self.socksPort), term.Color.YELLOW)))
                        reference = module(torNodesFound)
                        reference.serviceConnector.setSocksProxySettings(self.socksHost, self.socksPort)
                        reference.setPluginArguments(pluginArgs)
                        reference.processPluginArguments()
                        reference.serviceConnector.cli = self
                        reference.cli = self
                    else:
                        self.logger.info((term.format("[+] If you want to connect with Hidden Services in the deep web using the loaded plugin, you must start a TOR local instance manually. The default configuration used to connect with the TOR Socks Server is: " , term.Color.YELLOW)))
                        self.logger.info((term.format("[+] Host=%s , Port=%s" %(tortazoConfiguration.socksHost, tortazoConfiguration.socksPort), term.Color.YELLOW)))
                        self.logger.info((term.format("[+] You can change this configuration editing the 'socksHost' and 'socksPort' properties in 'config.py' module. Also, you can use -T/--tor-localinstance with your 'torrc' file and Tortazo will start a TOR instance for you and then, if you use the -U/--use-localinstance Tortazo will use the TOR local instance started to connect with hidden services in the deep web.", term.Color.YELLOW)))
                        reference = module(torNodesFound)
                        reference.serviceConnector.setSocksProxySettings(tortazoConfiguration.socksHost, tortazoConfiguration.socksPort)
                        reference.setPluginArguments(pluginArgs)
                        reference.processPluginArguments()
                        reference.serviceConnector.cli = self
                        reference.cli = self
                    if hasattr(self, 'database'):
                        reference.setDatabaseConnection(self.database)
                    reference.runPlugin()
                except StandardError as standarError:
                    self.logger.warn((term.format(standarError.message, term.Color.RED)))
                except PluginException as pluginExc:
                    self.logger.warn((term.format("[-] Exception raised executing the plugin. Please, check the arguments used in the function called. Details below.", term.Color.RED)))
                    self.logger.warn((term.format("Message: %s " %(pluginExc.getMessage()), term.Color.RED)))
                    self.logger.warn((term.format("Plugin: %s " %(pluginExc.getPlugin()), term.Color.RED)))
                    self.logger.warn((term.format("Method: %s " %(pluginExc.getMethod()), term.Color.RED)))
                    self.logger.warn((term.format("Trace: %s " %(pluginExc.getTrace()), term.Color.RED)))

                self.logger.debug((term.format("[+] Done!", term.Color.GREEN)))
            else:
                self.logger.warn((term.format("[-] The plugin specified is unknown... Check the available plugins with -L/--list-plugins option", term.Color.RED)))

        except ImportError, importErr:
            print "Unexpected error:", sys.exc_info()
            self.logger.warn((term.format("[-] Error loading the class. Your plugin class should be located in 'plugins' package and registered in pluginsDeployed.py. Check the available plugins with -L/--list-plugins option", term.Color.RED)))
        except AttributeError, attrErr:
            print "Unexpected error:", sys.exc_info()
            self.logger.warn((term.format("[-] Error loading the class. Your plugin class should be located in 'plugins' package and registered in pluginsDeployed.py. Check the available plugins with -L/--list-plugins option", term.Color.RED)))

if __name__ == "__main__":
    '''
    Start the main program.
    '''
    try:
        Cli.run()
    except AttributeError:
        print "[-] Invalid usage. Please, type the switch '--help'"
        import sys
        print sys.exc_info()

