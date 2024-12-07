import os


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret')
    MYSQL_USER = 'your_mysql_user'
    MYSQL_PASSWORD = 'your_mysql_password'
    MYSQL_DB = 'e_voting_system'
    MYSQL_HOST = 'localhost'
    MYSQL_PORT = 3306
