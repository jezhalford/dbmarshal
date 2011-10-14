import os.path
import sys
import os
import pickle
import MySQLdb as mysql

class DBMmarshal(object):

    __log_table_sql = """CREATE TABLE IF NOT EXISTS `dbmarshal_log` (
          `change_number` bigint(20) NOT NULL PRIMARY KEY,
          `started` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          `completed` timestamp NULL DEFAULT NULL,
          `description` varchar(500) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1"""
    
    def __get_config_root(self):
        """
        Returns the directory in which config files should be stored.
        """
        home = os.getenv("HOME")

        config_root = home + '/.dbmarshal'

        if not os.path.isdir(config_root):
           os.makedirs(config_root)

        return config_root

    def create_log_table(self):
        """
        Creates the log table.
        """
        try:
            conn = mysql.connect(self.__hostname, self.__username, self.__password, self.__database)

            cursor = conn.cursor()
            cursor.execute(self.__log_table_sql)

            conn.commit()
            cursor.close()
            conn.close()

        except mysql.Error, e:
            print "Error %d: %s" % (e.args[0],e.args[1])
            sys.exit(1)

    def save_config(self, alias):
        """
        Saves the current config in the config root, under the specified alias.
        """

        path = self.__get_config_root() + '/' + alias
        
        f = open(path, 'w')

        config = {
            'hostname' : self.__hostname,
            'username' : self.__username,
            'password' : self.__password,
            'database' : self.__database,
            'directory' : os.path.abspath(self.__directory),
        }

        pickle.dump(config, f)

        f.close()

    def setup(self, hostname, username, password, database, directory):
        """
        Sets up dbmarshal with all the info it needs.
        """
        self.__hostname = hostname
        self.__username = username
        self.__password = password
        self.__database = database
        self.__directory = os.path.abspath(directory)

    def parse_config(self, alias):
        """
        Takes a config file (from the supplied alias) and puts the settings from it into dbmarshal.
        """
        config = self.__get_config_root() + '/' + alias

        if os.path.exists(config):

            f = open(config, 'r')

            try:
                data = pickle.load(f)

                self.setup(data['hostname'], data['username'], data['password'], data['database'], data['directory'])

            except Exception:
                print '\nError: Could not find a valid config file called "' + alias + '"'

            f.close()
            
    def __applied_status(self):
        """
        Returns the migration number that was most recently applied to the database.
        """
        try:
            conn = mysql.connect(self.__hostname, self.__username, self.__password, self.__database)

            cursor = conn.cursor()
            cursor.execute('SELECT `change_number` FROM `dbmarshal_log` ORDER BY `change_number` DESC LIMIT 1')
            data = cursor.fetchone()
            cursor.close()
            conn.close()

            if data == None:
                data = 0
            else:
                data = int(data[0])

            return data

        except mysql.Error, e:
            print "Error %d: %s" % (e.args[0],e.args[1])
            sys.exit(1)


    def __available_status(self):
        """
        Returns the highest available migration number in the migrations directory.
        """
        listing = os.listdir(self.__directory)

        highest = 0

        for file in listing:
            if file.endswith('.sql'):
                raw = file.rstrip('.sql')
                if int(raw) > highest:
                    highest = int(raw)

        return highest

    def status(self):
        """
        Tells you all about where you are with migrations.
        """
        applied = self.__applied_status()

        available = self.__available_status()

        if applied == 0:
            print "\nThere is no record of any migrations having been applied to this database."
        else:
            print "\nDatabase is at migration number " + str(applied) + "."

        if available > 0:
            print "\nMigrations up to number " + str(available) + " are available."
        else:
            print "\nNo migrations are available to apply."


        print "\nThere are " + str(available - applied) + " migrations ready to apply."

        print "\n"

    def __get_migrations(self, start):
        """
        Returns all of the available migrations from a given start (inclusive) to the end, in
        ascending order.
        """
        migrations = []

        listing = os.listdir(self.__directory)

        listing.sort(key=lambda number: int(number.rstrip('.sql')))

        for file in listing:
            if file.endswith('.sql'):
                f = open(os.path.realpath(self.__directory + '/' + file), 'r')
                script = f.read()
                parts = script.partition('-- //@UNDO')
                number = file.rstrip('.sql')
                if int(number) >= start:
                    migrations.append({
                                'do' : parts[0],
                                'undo' : parts[2],
                                'name' : file,
                                'number' : number
                                })
        return migrations
                

    def __run_scripts(self, migrations, type):
        """
        Runs scripts of the specified type in a transaction
        """
        try:
            conn = mysql.connect(self.__hostname, self.__username, self.__password, self.__database)
            
            cursor = conn.cursor()

            for migration in migrations:
                print "Applying migration: " + migration['name'] + "...\n"

                log_update_one = """
                INSERT INTO `dbmarshal_log` SET `change_number` = %d, `description` = '%s';
                """ % (int(migration['number']), migration['name'])

                log_update_two = """
                UPDATE `dbmarshal_log` SET `completed` = NOW() WHERE `change_number`= %d;
                """ % (int(migration['number']))
                cursor.execute(log_update_one)
                cursor.execute(migration[type])
                cursor.execute(log_update_two)


            conn.commit()

        except mysql.Error, e:
            print "Error %d: %s" % (e.args[0],e.args[1])
            try:
                print '\nSome of the migrations seem to have failed. Those that can be rolled back will be.\n'
                conn.rollback()
            except  mysql.Error, e:
                print "Error %d: %s" % (e.args[0],e.args[1])

            sys.exit(1)

        cursor.close()
        conn.close()
        
    def apply(self):
        """
        Applies outstanding migrations to the database.
        """
        applied = self.__applied_status()
        outstanding_migrations = self.__get_migrations(applied+1)

        if len(outstanding_migrations) == 0:
            print "\ndbmarshal: There are no undeployed database migrations available.\n"
        else:
            print "\ndbmarshal: Applying database migrations.\n"
            self.__run_scripts(outstanding_migrations, 'do')
            print "\nDone.\n"

    def describe(self):
        """
        Explain the currently loaded settings.
        """
        print "\nYour alias results in the following settings:\n"
        print "Hostname:\t\t" + self.__hostname
        print "Username:\t\t" + self.__username
        print "Password:\t\t" + '*' * len(self.__password)
        print "Database:\t\t" + self.__database
        print "Migrations Directory:\t" + self.__directory
        print "\n"

