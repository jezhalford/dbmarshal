

dbmarshal
=========

dbmarshal is a migration tool for mySQL databases.

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

dbmarshal does not provision for undoing migrations, but does *attempt* to roll back if things go
wrong -see **Transactions** below.

Requirements
------------

The following describes how to start using dbmarshal in Ubuntu. I imagine these steps are broadly
similar for other linux flavours.

You will need...

*Python*

The following installs Python along with a popular mySQL library.

    sudo apt-get install python python-mysqldb


Configuration
-------------

Clone or otherwise acquire the dbmarshal source. Life will become easier if you add this directory
to your PATH. Assuming you have done this, and with the following information to hand...


    hostname  : The hostname of the database server you want to work with.
    username  : The username you need to use to access this server.
    password  : The corresponding password.
    database  : The name of the schema you want to work with.
    directory : The path at which you will keep your migration files.
    alias     : A handy name with which you can reference these settings later.

...run...

    dbmarshal init <hostname> <username> <password> <database> <directory > <alias>

...this will create a file at

    ~/.dbmarshal/<alias>

...that will store the information you speicify. It will also create a new table in your database
called `dbmarshal_log` that will be used to keep track of your migrations.


Using dbmarshal
---------------

Assuming you have done the above configuration:

    dbmarshal <alias> describe

...will display the settings you previously entered.

    dbmarshal <alias> status

...will tell you about migrations that have and have not been applied.

    dbmarshal <alias> apply

...will apply any waiting migrations that have yet to be applied.

    dbmarshal <alias> export_statics

...will create correctly named static migration files for all stored procedures and triggers in your
database.

    dbmarshal <alias> create_log_table

...will create a blank log table in your database. This is done automatically when you
`dbmarshal init`.

    dbmarshal <alias> save_config <new_alias>

...will copy the settings saved under `<alias>` to a `<new_alias>`.

Migration Files
---------------

There are two kinds of migrations that dbmarshal is willing to deal with. *Static Migrations*,
and *Revisions*. These will need to be placed into two directories under your migration files path.
Your migrations directory therefore should be structured like this -

    my_migrations_directory/
        statics/
        revisions/

###Statics###

These are SQL scripts that create either stored procedures or triggers, and should be named things
like `trigger__my_trigger.sql` or `sproc__this_procedure.sql`. All SQL filenames in this directory
must start with either `trigger__` or `sproc__`. It is probably a good idea to use the rest of the
file name to store the name of the trigger or procedure that the file creates, and it is certainly
a bad idea to create more than one of anything in any one file.

###Revisions###

These are SQL scripts named numerically - `1.sql`, `2.sql`, etc. They should each represent a change
that needs to be made to your database structure, which may depend on the existing structure e.g.
adding tables, changing columns, etc.

Transactions
------------

Each time you run `dbmarshal <alias> apply` a new transaction is started. If any one of the
migrations that are due to be deployed in that session fails, the transaction will be rolled back,
 i.e. *None of them will be applied*.
However, mySQL does not support transactions for DDL operations, i.e. `CREATE TABLE`, `ALTER TABLE`,
etc. If the migration set contains any such operations the rollback will fail. You will then end up
with an entry in your log table that has a `started` time but no `completed` time.

If a migration fails its log entry will be deleted and the error message returned by mySQL will be
displayed in your terminal.
