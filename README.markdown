dbmarshal
=========

dbmarshal is a dbdeploy inspired database migration tool. It supports mySQL, makes use of transactions, and is written in python.


Requirements
------------

The following describes how to start using dbmarshal in Ubuntu. I imagine these steps are broadly similar for other linux flavours.

You will need...

*Python*

The following installs Python along with a popular mySQL library.

    sudo apt-get install python python-mysqldb


Configuration
-------------

Clone or otherwise acquire the dbmarshal source. Life will become easier if you add this directory to your PATH. Assuming you have done this, and with the following information to hand...


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

...that will store the information you speicify. It will also create a new table in your database called `dbmarshal_log` that will be used to keep track of your migrations.


Using dbmarshal
---------------

Assuming you have done the above configuration:

    dbmarshal <alias> describe

...will display the settings you previously entered.

    dbmarshal <alias> status

...will tell you about migrations that have and have not been applied.

    dbmarshal <alias> apply

...will apply any waiting migrations that have yet to be applied.

Migration Files
---------------

These should be named `x.sql`, where `x` is the number of the migration, e.g. `1.sql`, `2.sql`, etc. Each migration should contain the SQL required to make the migration happen, followed by `-- //@UNDO`, followed by the SQL required to undo the migration. (Undoing isn't actually supported by dbmarshal yet, but hopefully it will be soon.) The `-- //@UNDO` line is REQUIRED - dbmarshal will break if it is not there.

Transactions
------------

Each time you run `dbmarshal <alias> apply` a new transaction is started. If any one of the migrations that are due to be deployed in that session fails, the transaction will be rolled back, i.e. *None of them will be applied*.

If a migration fails the error message returned by mySQL will be displayed in your terminal.

