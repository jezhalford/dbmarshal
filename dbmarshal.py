import sys
import os
import pickle
import MySQLdb as mysql
from warnings import filterwarnings, resetwarnings

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
        DBMarshal.talk("Setting up alias: " + alias)

        dbm = DBMarshal(hostname, username, password, database, os.path.abspath(directory))
        dbm.clone(alias)

        DBMarshal.done('New alias created successfully.')

        return dbm

    @staticmethod
    def from_alias(alias):
        """
        Takes a config file (from the supplied alias) and puts the settings from it into dbmarshal.
        """
        config = DBMarshal.get_config_root() + '/' + alias

        if os.path.exists(config):

            f = open(config, 'r')

            data = pickle.load(f)
            f.close()
            return DBMarshal.factory(data['hostname'], data['username'],
                                        data['password'], data['database'], data['directory'])
        else:
            
            DBMarshal.error('Could not find a valid config file called "' + alias + '"')

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

    @staticmethod
    def talk(heading, messages = []):

        if heading is not None:
            print "\n\033[1mdbmarshal:\033[0m " + heading

        for message in messages:
            print "\t" + message

    @staticmethod
    def error(message):
        sys.stderr.write('\n\033[91m\033[1mERROR:\033[0m\033[91m ' + message + '\033[0m\n')
        sys.exit(1)

    @staticmethod
    def warn(message):
        sys.stderr.write('\n\033[93m\033[1mWARNING:\033[0m\033[93m ' + message + '\033[0m\n')

    @staticmethod
    def done(message):
        print "\n\t\033[92m" + message + "\033[0m"

    def __get_db_connection(self):
        try:
            return mysql.connect(self.__hostname, self.__username, self.__password, self.__database)
        except mysql.Error, e:
            DBMarshal.error("Error %d: %s" % (e.args[0],e.args[1]))

    def __get_revisions_dir(self):
        return self.__directory + '/revisions'

    def __get_statics_dir(self):
        return self.__directory + '/statics'

    def __applied_status(self):
        """
        Returns the revision number that was most recently applied to the database.
        """
        try:
            conn = self.__get_db_connection()

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
            DBMarshal.error("Error %d: %s" % (e.args[0],e.args[1]))

    def __available_status(self):
        """
        Returns the highest available revision number in the revisions directory.
        """
        listing = os.listdir(self.__get_revisions_dir())

        highest = 0

        for file in listing:
            if file.endswith('.sql'):
                raw = file.rstrip('.sql')
                if int(raw) > highest:
                    highest = int(raw)

        return highest

    def __get_static_status(self):
        """
        Returns a count of static scripts that need to be applied.
        """
        feedback = {'sprocs' : 0, 'triggers' : 0}

        listing = os.listdir(self.__get_statics_dir())

        for file in listing:
            if file.endswith('.sql') and file.startswith('trigger__'):
                feedback['triggers'] += 1
            elif file.endswith('.sql') and file.startswith('sproc__'):
                feedback['sprocs'] += 1

        return feedback

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
                scripts.append({'script' : script, 'file' : file})
                
        return scripts

    def __get_statics(self):
        """
        Gets a list of any triggers or stored procedures that exist on the database.
        """
        try:

            conn = self.__get_db_connection()

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

            return {'triggers' : triggers, 'sprocs' : sprocs}
            
        except mysql.Error, e:
            conn.rollback()
            DBMarshal.error("Error %d: %s" % (e.args[0],e.args[1]) +
                '\n\nCould not get a list of static objects.')

        cursor.close()
        conn.close()


    def __drop_statics(self):
        """
        Drops any triggers or stored procedures that exist on the database.
        """
        try:

            conn = self.__get_db_connection()
            cursor = conn.cursor()
            
            statics = self.__get_statics()

            for sproc in statics['sprocs']:
                cursor.execute('DROP PROCEDURE %s' % sproc[0])

            for trigger in statics['triggers']:
                cursor.execute('DROP TRIGGER %s' % trigger[0])
            
            cursor.close()

            conn.commit()

            return {'triggers' : len(statics['triggers']),
                    'sprocs' : len(statics['sprocs'])}

        except mysql.Error, e:
            conn.rollback()
            DBMarshal.error("Error %d: %s" % (e.args[0],e.args[1]) +
                '\n\nFailed to drop static objects.')
            
            sys.exit(1)

        cursor.close()
        conn.close()

    def __create_statics(self):
        """
        Creates triggers and stored procedures from the static migrations.
        """
        try:
            conn = self.__get_db_connection()

            cursor = conn.cursor()

            feedback = {'sprocs' : 0, 'triggers' : 0}

            for script in self.__get_static_scripts():
                if script['file'].startswith('trigger__'):
                    feedback['triggers'] += 1
                elif script['file'].startswith('sproc__'):
                    feedback['sprocs'] += 1
                else:
                    print "Found a static migration file called '" + script['file'] + "'. Static migrations must start with trigger__ or sproc__."
                    exit(1)

                cursor.execute(script['script'])
            
            cursor.close()

            conn.commit()

            return feedback

        except mysql.Error, e:
            conn.rollback()
            DBMarshal.error("Error %d: %s" % (e.args[0],e.args[1]) +
                "\n\nFailed to run static migration '" + script['file'] + "'.")

        cursor.close()
        conn.close()

    def __run_scripts(self, migrations):
        """
        Runs scripts of the specified type in a transaction
        """
        try:
            conn = self.__get_db_connection()
            
            cursor = conn.cursor()

            for migration in migrations:
                DBMarshal.talk(None, ["Applying revision: " + migration['name'] + "..."])

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
            try:
                conn.rollback()
                cursor.execute('DELETE FROM `dbmarshal_log` WHERE `change_number`= %d;'
                                   % (int(migration['number'])))

                DBMarshal.error("Error %d: %s" % (e.args[0],e.args[1]) +
                '\n\nSome of the migrations seem to have failed. Those that can be rolled back will be.')
            except  mysql.Error, e:
                DBMarshal.error("Error %d: %s" % (e.args[0],e.args[1]))


        cursor.close()
        conn.close()

    def __statics_mismatch(self):
        """
        Returns true if there are no static migration files but static objects exist in the daatabse
        """
        statics = self.__get_static_status()
        applied_statics = self.__get_statics()
        return (statics['triggers'] == 0 or statics['sprocs'] == 0) and (len(applied_statics['triggers']) > 0 or len(applied_statics['sprocs']) > 0)

    def export_statics(self):
        """
        Create scripts for sprocs and triggers that currently exist into the database.
        """

        DBMarshal.talk('export_statics', ["Exporting statics to '%s'." % self.__get_statics_dir()])

        try:

            conn = self.__get_db_connection()

            cursor = conn.cursor()

            statics = self.__get_statics()

            for sproc in statics['sprocs']:
                cursor.execute('SHOW CREATE PROCEDURE %s' % sproc[0])
                sproc_info = cursor.fetchone()

                f = open(self.__get_statics_dir() + '/sproc__' + sproc_info[0] + '.sql' , 'w')
                f.write(sproc_info[2])
                f.close()


            for trigger in  statics['triggers']:
                cursor.execute('SHOW CREATE TRIGGER %s' % trigger[0])
                trigger_info = cursor.fetchone()

                f = open(self.__get_statics_dir() + '/trigger__' + trigger_info[0] + '.sql' , 'w')
                f.write(trigger_info[2])
                f.close()

            DBMarshal.done('Static migrations successfully created.')

        except mysql.Error, e:
            conn.rollback()
            DBMarshal.error("Error %d: %s" % (e.args[0],e.args[1]) +
                '\n\nFailed to drop static objects, rolling back.')
            
        cursor.close()
        conn.close()


    def apply(self):
        """
        Applies outstanding migrations to the database.
        """
        self.create_log_table()

        if self.__statics_mismatch():
            not_answered = True
            while not_answered:
                DBMarshal.talk("apply")
                DBMarshal.warn('Triggers and/or stored procedures exist in your database but you do not have any corresponding static migrations.' +
                '\n\t Continuing will drop all triggers and stored procedures from your database.' +
                '\n\t To prevent this, answer no and use dbmarshal export_statics to create static migrations for all existing stored procedures and triggers.\n')
                answer = raw_input("\t Do you wish to DROP ALL TRIGGERS AND STORED PROCEDURES FROM YOUR DATABASE? (y/n) ").upper()

                if answer == 'Y':
                    not_answered = False

                if answer == 'N':
                    exit(0)

            

        applied = self.__applied_status()
        outstanding_migrations = self.__get_revisions(applied+1)

        DBMarshal.talk("apply",
            ["Running migration scripts..."])

        drop_feedback = self.__drop_statics()

        DBMarshal.talk(None, [("Dropped %d stored procedures and %s triggers." %
                     (drop_feedback['sprocs'], drop_feedback['triggers']))])

        create_feedback = self.__create_statics()

        DBMarshal.talk(None, [("Created %d stored procedures and %s triggers." %
                     (create_feedback['sprocs'], create_feedback['triggers']))])

        if len(outstanding_migrations) == 0:
            DBMarshal.talk(None, ['There are no undeployed revisions available.'])
        else:
            DBMarshal.talk(None, ['Applying revisions'])
            self.__run_scripts(outstanding_migrations)

        DBMarshal.done('Database updated successfully.')

    def describe(self):
        """
        Explain the currently loaded settings.
        """
        DBMarshal.talk('Your alias results in the following settings:', [
            "Hostname:\t\t" + self.__hostname,
            "Username:\t\t" + self.__username,
            "Password:\t\t" + '*' * len(self.__password),
            "Database:\t\t" + self.__database,
            "Migrations Directory:\t" + self.__directory,
        ])

    def status(self):
        """
        Tells you all about where you are with migrations.
        """
        self.create_log_table()
        
        applied = self.__applied_status()

        available = self.__available_status()

        statics = self.__get_static_status()

        applied_statics = self.__get_statics()

        messages = []

        messages.append("The database is at revision " + str(applied) + ".")

        if available > 0:
            messages.append("Revisions up to number " + str(available) + " are available.")
        else:
            messages.append("0 revisions are available to apply.")

        messages.append(str(available - applied) + " revisions need to be applied.")

        messages.append("%d trigger scripts are available to run."
                                                                        % statics['triggers'])
        messages.append("%d stored procedure scripts are available to run."
                                                                        % statics['sprocs'])

        messages.append("%d triggers exist in the database."
                                                            % len(applied_statics['triggers']))

        messages.append("%d stored procedures exist in the database."
                                                            % len(applied_statics['sprocs']))

        DBMarshal.talk('status', messages)

        if self.__statics_mismatch():
            DBMarshal.warn('Triggers and/or stored procedures exist in your database but you do not have any corresponding static migrations.' +
            '\n\t Using dbmarshal apply now will drop all triggers and stored procedures from your database.' +
            '\n\t To prevent this, Use dbmarshal export_statics to create static migrations for all existing stored procedures and triggers.')
        

    def create_log_table(self):
        """
        Creates the log table.
        """
        try:
            filterwarnings('ignore', category = mysql.Warning)
            conn = self.__get_db_connection()

            cursor = conn.cursor()
            cursor.execute(self.__log_table_sql)

            conn.commit()
            cursor.close()
            conn.close()
            resetwarnings()

        except mysql.Error, e:
            DBMarshal.error("Error %d %s" % (e.args[0],e.args[1]))

    def clone(self, alias):
        """
        Saves the current config under a new specified alias.
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

        DBMarshal.talk('clone');
        DBMarshal.done('Config successfully saved as "' + alias + '".')