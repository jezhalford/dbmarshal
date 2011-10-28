dbmarshal
=========

dbmarshal is a migration tool for MySQL databases.

It works a lot like dbdeploy. It creates a log table in your database that it uses to keep
track of what revision number the database is at. It allows you to store database revisions as
numerically named SQL files and, when asked, will bring your database up to date by running
any such migrations that have not yet been applied.

dbmarshal handles *triggers* and *stored procedures* separately to other types of migration. You can
use ordinary numerical revisions to create such things, but this is probably a bad idea - what if
you subsequently change the structure of tables that the sprocs and triggers rely on? You'll
probably have to search backward through your revisions until you find any that are affected, and
then create another revision that drops and recreates them to work with the new structure.

Rather than bother with all this, dbmarshal stores triggers and sprocs as *static* migrations -
each time you apply an update all the sprocs and triggers on your database are dropped and rebuilt
from static (i.e. not numerically named) scripts. This has the advantage that you can easily see
and read the source of all your triggers and sprocs, and make any changes without having to drop and
recreate the item concerned.

dbmarshal does not provision for undoing migrations, but can *attempt* to roll back if things go
wrong -see **Transactions** below.

Requirements
------------

The install script will install everything you need to run dbmarshal on Ubuntu. For other platforms, 
you'll need to find a means of installing the following...

*Python*, the *MySQLdb* Python package and the *sqlparse* Python package.

*Python* and *MySQLdb* are readily available in your favourite package manager.

See http://code.google.com/p/python-sqlparse/ for ways to get hold of *sqlparse*.

Configuration
-------------

Clone or otherwise acquire the dbmarshal source. Life will become easier if you add this directory
to your PATH. This is done automatically if you use the install script. Assuming you have done 
this, and with the following information to hand...


    hostname  : The hostname of the database server you want to work with.
    username  : The username you need to use to access this server.
    password  : The corresponding password.
    database  : The name of the schema you want to work with.
    directory : The path at which you will keep your migration files. This will be created for you
                if it doesn't exist.
    alias     : A handy name with which you can reference these settings later. Use 'default' if you
                don't want to bother typing it in later.

...run...

    dbmarshal init <hostname> <username> <password> <database> <directory > <alias>

...this will create a file at

    ~/.dbmarshal/<alias>

...that will store the information you speicify, ready for use.


Migration Files
---------------

There are two kinds of migrations that dbmarshal is willing to deal with. *Static Migrations*,
and *Revisions*. These will need to be placed into two directories under your migration files path.
Your migrations directory therefore should be structured like this -

    my_migrations_directory/
        stored-procedures/
        triggers/
        revisions/

If the required directory structure does not exist when you `dbmarshal init` it will be created for 
you.

###Stored Procedures and Triggers###

These are SQL scripts that create either stored procedures or triggers, and can be named whatever
you like, as long as you use an `.sql` suffix. It is probably a good idea name the file after the
trigger or stored procedure that it creates, and it is certainly a bad idea to create more than one
of anything in any one file.

###Revisions###

These are SQL scripts named numerically - `00001.sql`, `000002.sql`, etc. They should each represent
a change that needs to be made to your database structure, which may depend on the existing
structure e.g. adding tables, changing columns, etc. Leading zeros are optional - add as many or as
few as seems appropriate.


Using dbmarshal
---------------

Assuming you have done the above configuration, having supplied `default` as your alias...

    dbmarshal describe

...will display the settings you previously entered.

    dbmarshal status

...will tell you about migrations that have and have not been applied.

    dbmarshal apply

...will apply any waiting migrations that have yet to be applied.

    dbmarshal export_statics

...will create correctly named static migration files for all stored procedures and triggers in your
database.

    dbmarshal create_log_table

...will create a blank log table in your database. This is done automatically the first time you
use `status` or `apply`.

    dbmarshal clone <new_alias>

...will copy the settings saved under `<alias>` to a `<new_alias>`. If you specify 'default' as the
alias then you don't need to bother entering an alias for any other commands.

###Using Other Aliases###

If you choose not to use `default` as your alias, or if you want to use dbmarshal to manage more
than one database, you'll need to specify the alias as the first parameter to dbmarsal, e.g.

    dbmarshal <alias> status


Transactions
------------

dbmarshal does not make use of transactions. It operates with autocommit enabled, so each SQL
statement is committed as soon as it has executed.

This is simply because MySQL's transaction support is not very good. It supports transactions only
for a few operations on InnoDB tables. Certain `ALTER TABLE` operations, `CREATE TABLE` operations
and various other statements cannot be part of a transaction. Transaction support can only really be
relied on for data manipulation operations - `SELECT`ing, `INSERT`ing etc. and the majority of work
anyone is likely to do with a tool such as dbmarshal is probably not going to be of this type.

To keep things simple, dbmarshal leaves transactions up to you: if you want a revision to use a
transaction, surround it with `BEGIN` and `COMMIT`. dbmarshal *will* call `ROLLBACK` in the event
of a revision failing, but unless you have explicitly started a transaction this will not have any
effect.
