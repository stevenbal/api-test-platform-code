from vng.k8s_manager.kubernetes import *

postgis = Container(
    name='postgis',
    image='mdillon/postgis:11',
    public_port=None,
    private_port=None,
    variables={
        'POSTGRES_PASSWORD': 'postgres',
        'POSTGRES_USER': 'postgres'
    },
    data=[
        "create database AC;"
        "create database NRC;"
        "create database ZTC;"
        "create database ZRC;"
        "create database DRC;"
        "create database BRC;"
    ],
    filename='initdb.sql'
)

rabbitMQ = Container(
    name='rabbit',
    image='rabbitmq',
    public_port=None,
    private_port=None,
    variables={}
)

NRC_CELERY = Container(
    name='celery',
    image='vngr/gemma-notifications',
    public_port=None,
    private_port=None,
    variables={
        'DB_HOST': 'localhost',
        'DB_NAME': 'nrc',
        'DB_USER': 'postgres',
        'DB_PASSWORD': 'postgres',
        'DJANGO_SETTINGS_MODULE': 'notifications.conf.docker',
        'UWSGI_PORT': '8004',
        'IS_HTTPS': '0',
        'SECRET_KEY': '^6gn!(9zn%h(-u0t=iq3f(7izgi-#a2n6@fxlh5z7fxp=#evf#',
        'PUBLISH_BROKER_URL': 'amqp://guest@localhost:5672//',
        'CELERY_BROKER_URL': 'amqp://guest@localhost:5672//',
        'CELERY_RESULT_BACKEND': 'amqp://guest@localhost:5672//',
    },
    command=[
        'celery',
        'worker',
        '-A',
        'notifications',
        '--workdir=src'
    ]
)

NRC = Container(
    name='nrc',
    image='vngr/gemma-notifications',
    public_port=8004,
    private_port=8004,
    variables={
        'DB_HOST': 'localhost',
        'DB_NAME': 'nrc',
        'DB_USER': 'postgres',
        'DB_PASSWORD': 'postgres',
        'DJANGO_SETTINGS_MODULE': 'notifications.conf.docker',
        'UWSGI_PORT': '8004',
        'IS_HTTPS': '0',
        'SECRET_KEY': 'x1#8uih#76j4z)+_3j-^iot)2=c#ht%&j1lcvyqxh&t+=5i@i=',
        'PUBLISH_BROKER_URL': 'amqp://guest:guest@nrc_rabbitmq:5672//',
        'CELERY_BROKER_URL': 'amqp://guest:guest@nrc_rabbitmq:5672//',
        'CELERY_RESULT_BACKEND': 'amqp://guest:guest@nrc_rabbitmq:5672//',
    }
)

ZTC = Container(
    name='ztc',
    image='vngr/gemma-ztc',
    public_port=8002,
    private_port=8002,
    variables={
        'DB_HOST': 'localhost',
        'DB_NAME': 'ztc',
        'DB_USER': 'postgres',
        'DB_PASSWORD': 'postgres',
        'DJANGO_SETTINGS_MODULE': 'ztc.conf.docker',
        'UWSGI_PORT': '8002',
        'IS_HTTPS': '0',
        'SECRET_KEY': '5t=%u76*^l%d97mp)6%u4-p^&wgfh(!+t1$*0pgjt&0&=oh-f!'
    }
)

ZRC = Container(
    name='zrc',
    image='vngr/gemma-zrc',
    public_port=8000,
    private_port=8000,
    variables={
        'DB_HOST': 'localhost',
        'DB_NAME': 'zrc',
        'DB_USER': 'postgres',
        'DB_PASSWORD': 'postgres',
        'DJANGO_SETTINGS_MODULE': 'zrc.conf.docker',
        'UWSGI_PORT': '8000',
        'IS_HTTPS': '0',
        'SECRET_KEY': '6$10p3m()ygr41f&!(ya=dw=aysz_9rg+bj1x*o1^vnw1n3-!p'
    }
)

BRC = Container(
    name='brc',
    image='vngr/gemma-brc',
    public_port=8003,
    private_port=8003,
    variables={
        'DB_HOST': 'localhost',
        'DB_NAME': 'brc',
        'DB_USER': 'postgres',
        'DB_PASSWORD': 'postgres',
        'DJANGO_SETTINGS_MODULE': 'brc.conf.docker',
        'UWSGI_PORT': '8003',
        'IS_HTTPS': '0',
        'SECRET_KEY': 'dtd5g0#bef=sj!ii5@8pl3bkp=@$u7e68&+2p735n4ff1s22a3'
    }
)

DRC = Container(
    name='drc',
    image='vngr/gemma-drc',
    public_port=8001,
    private_port=8001,
    variables={
        'DB_HOST': 'localhost',
        'DB_NAME': 'drc',
        'DB_USER': 'postgres',
        'DB_PASSWORD': 'postgres',
        'DJANGO_SETTINGS_MODULE': 'drc.conf.docker',
        'UWSGI_PORT': '8001',
        'IS_HTTPS': '0',
        'SECRET_KEY': 'h3af@_s8s@@(g0sz4py$6eaimers9zx8zu5m=3yi+kd(tjudlh'
    }
)

AC = Container(
    name='ac',
    image='vngr/gemma-autorisatiecomponent',
    public_port=8005,
    private_port=8005,
    variables={
        'DB_HOST': 'localhost',
        'DB_NAME': 'ac',
        'DB_USER': 'postgres',
        'DB_PASSWORD': 'postgres',
        'DJANGO_SETTINGS_MODULE': 'ac.conf.docker',
        'UWSGI_PORT': '8005',
        'IS_HTTPS': '0',
        'SECRET_KEY': 'l00=^9g$va8nzl8#n1g_2e=8fdq$$38&^x6x$t9-cm6=tg8$hu'
    }
)
