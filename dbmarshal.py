import sys
import os
import pickle
import MySQLdb as mysql

class DBMarshal(object):

    __log_table_sql = """CREATE TABLE IF NOT EXISTS `dbmarshal_log` (
          `change_number` bigint(20) NOT NULL PRIMARY KEY,
          `started` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          `completed` timestamp NULL DEFAULT NULL,
          `description` varchar(500) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1"""

    def __init__(self, hostname, username, password, database, directory):
        """
        Constructor
        """
        self.__hostname = hostname
        self.__username = username
        self.__password = password
        self.__database = database
        self.__directory = os.path.abspath(directory)

    @staticmethod
    def factory(hostname, username, password, database, directory):
        """
        Sets up and returns a new dbmarshal with all the info it needs.
        """
        return DBMarshal(hostname, username, password, database, os.path.abspath(directory))

    @staticmethod
    def create_alias(hostname, username, password, database, directory, alias):
        """
        Sets up and returns a new dbmarshal with all the info it needs.
        """
        print "\ndbmarshal: Setting up alias: " + alias + "\n"

        dbm = DBMarshal(hostname, username, password, database, os.path.abspath(directory))
        dbm.save_config(alias)
        dbm.create_log_table()

        print "\nDone.\n"

        return dbm

    @staticmethod
    def from_alias(alias):
        """
        Takes a config file (from the supplied alias) and puts the settings from it into dbmarshal.
        """
        config = DBMarshal.get_config_root() + '/' + alias

        print config

        if os.path.exists(config):

            f = open(config, 'r')

            data = pickle.load(f)

            return DBMarshal.factory(data['hostname'], data['username'],
                                        data['password'], data['database'], data['directory'])

        else:
            print '\nError: Could not find a valid config file called "' + alias + '"'

            f.close()

    @staticmethod
    def get_config_root():
        """
        Returns the directory in which config files should be stored.
        """
        home = os.getenv("HOME")

        config_root = home + '/.dbmarshal'

        if not os.path.isdir(config_root):
           os.makedirs(config_root)

        return config_root

    def __get_revisions_dir(self):
        return self.__directory + '/revisions'

    def __get_statics_dir(self):
        return self.__directory + '/statics'

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
        listing = os.listdir(self.__get_revisions_dir())

        highest = 0

        for file in listing:
            if file.endswith('.sql'):
                raw = file.rstrip('.sql')
                if int(raw) > highest:
                    highest = int(raw)

        return highest

    def __static_status(self):
        """
        Returns a count of static scripts that need to be applied.
        """
        return len(os.listdir(self.__get_statics_dir()))

    def __get_revisions(self, start):
        """
        Returns all of the available revisions from a given start (inclusive) to the end, in
        ascending order.
        """
        revisions = []

        listing = os.listdir(self.__get_revisions_dir())

        listing.sort(key=lambda number: int(number.rstrip('.sql')))

        for file in listing:
            if file.endswith('.sql'):
                f = open(os.path.realpath(self.__get_revisions_dir() + '/' + file), 'r')
                script = f.read()
                number = file.rstrip('.sql')
                if int(number) >= start:
                    revisions.append({
                                'script' : script,
                                'name' : file,
                                'number' : number
                                })
        return revisions

    def __get_static_scripts(self):
        """
        Returns all of the static migration scripts.
        """
        scripts = []

        listing = os.listdir(self.__get_statics_dir())

        for file in listing:
            if file.endswith('.sql'):
                f = open(os.path.realpath(self.__get_statics_dir() + '/' + file), 'r')
                script = f.read()
                scripts.append(script)
                
        return scripts
                

    def __drop_statics(self):
        """
        Drops any triggers, stored procedures or views that exist on the database.
        """
        try:

            conn = mysql.connect(self.__hostname, self.__username, self.__password, self.__database)

            # sprocs
            cursor = conn.cursor()
            cursor.execute("""SELECT R.SPECIFIC_NAME FROM INFORMATION_SCHEMA.ROUTINES R
                                WHERE R.ROUTINE_SCHEMA = '%s' AND R.ROUTINE_TYPE = 'PROCEDURE'"""
                                % (self.__database))
                                
            sprocs = cursor.fetchall()

            #triggers
            cursor.execute("""SELECT T.TRIGGER_NAME FROM INFORMATION_SCHEMA.TRIGGERS T
                                WHERE TRIGGER_SCHEMA = '%s'""" % (self.__database))
            triggers = cursor.fetchall()

            #views
            cursor.execute("""SELECT V.TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS V
                                WHERE V.TABLE_SCHEMA = '%s'""" % (self.__database))
            views = cursor.fetchall()

            for sproc in sprocs:
                print ('DROP PROCEDURE %s' % sproc[0])

            for trigger in triggers:
                print ('DROP TRIGGER %s' % trigger[0])

            for view in views:
                print ('DROP VIEW  %s' % view[0])
            
            cursor.close()

            conn.commit()

            return {'triggers' : len(triggers), 'sprocs' : len(sprocs), 'vies' : len(views)}

        except mysql.Error, e:
            print "Error %d: %s" % (e.args[0],e.args[1])
            print '\nFailed to drop static objects, rolling back.\n'
            conn.rollback()
            sys.exit(1)

        cursor.close()
        conn.close()

    def __create_statics(self):
        """
        Creates triggers, stored procedures and views from the static migrations.
        """
        try:
            conn = mysql.connect(self.__hostname, self.__username, self.__password, self.__database)

            cursor = conn.cursor()

            for script in self.__get_static_scripts():
                cursor.execute(script)
            
            cursor.close()

            conn.commit()

        except mysql.Error, e:
            print "Error %d: %s" % (e.args[0],e.args[1])
            print '\nFailed to create static objects, rolling back.\n'
            conn.rollback()
            sys.exit(1)

        cursor.close()
        conn.close()

    def __run_scripts(self, migrations):
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
                cursor.execute(migration['script'])
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
        outstanding_migrations = self.__get_revisions(applied+1)

        print "\ndbmarshal: Dropping and restoring triggers, stored procedures and views.\n"
        drop_feedback = self.__drop_statics()

        print "\ndbmarshal: Dropped " + str(drop_feedback['sprocs']) + " stored procedures.\n"
        print "\ndbmarshal: Dropped " + str(drop_feedback['triggers']) + " triggers.\n"
        print "\ndbmarshal: Dropped " + str(drop_feedback['views']) + " views.\n"

        create_feedback = self.__create_statics()
        print "\ndbmarshal: Created " + str(create_feedback['sprocs']) + " stored procedures.\n"
        print "\ndbmarshal: Created " + str(create_feedback['triggers']) + " triggers.\n"
        print "\ndbmarshal: Created " + str(create_feedback['views']) + " views.\n"

        print "\nDone.\n"

        if len(outstanding_migrations) == 0:
            print "\ndbmarshal: There are no undeployed revisions available.\n"
        else:
            print "\ndbmarshal: Applying revisions.\n"
            self.__run_scripts(outstanding_migrations)
            print "\nDone.\n"

    def describe(self):
        """
        Explain the currently loaded settings.
        """
        print "\ndbmarshal: Your alias results in the following settings:\n"
        print "\tHostname:\t\t" + self.__hostname
        print "\tUsername:\t\t" + self.__username
        print "\tPassword:\t\t" + '*' * len(self.__password)
        print "\tDatabase:\t\t" + self.__database
        print "\tMigrations Directory:\t" + self.__directory
        print "\n"

    def status(self):
        """
        Tells you all about where you are with migrations.
        """
        applied = self.__applied_status()

        available = self.__available_status()

        statics = self.__static_status()

        print "\ndbmarshal: Status..."

        if applied == 0:
            print "\n\tThere is no record of any revisions having been applied to this database."
        else:
            print "\n\tDatabase is at revision number " + str(applied) + "."

        if available > 0:
            print "\n\tRevisions up to number " + str(available) + " are available."
        else:
            print "\n\tNo revisions are available to apply."


        print "\n\tThere are " + str(available - applied) + " revisions ready to apply."

        print "\n\tThere are " + str(statics) + " static migrations to run."

        print "\n"

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
            print "Error %d %s" % (e.args[0],e.args[1])
            sys.exit(1)

    def save_config(self, alias):
        """
        Saves the current config in the config root, under the specified alias.
        """

        path = DBMarshal.get_config_root() + '/' + alias

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
        