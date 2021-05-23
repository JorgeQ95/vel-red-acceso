#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__all__ = ('get_speeds', 'run_schedule')

import logging
import sqlite3
import sys
import time
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import NoReturn

import schedule
import speedtest

Data = namedtuple('Data', ('timestamp', 'download', 'upload', 'ping', 'server_id'))
Server = namedtuple('Server', ('puerto', 'url', 'latitud', 'longitud', 'ubicacion'))

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format='%(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M',
)
logger = logging.getLogger()

_db = Path('bandwidth.db')
if not _db.exists():
	logger.info('Iniciando formato de almacenamiento de datos')

	conn = sqlite3.connect(_db)

	crsr = conn.executescript('''
		PRAGMA foreign_keys = ON;

		CREATE TABLE IF NOT EXISTS server (
			id INTEGER PRIMARY KEY,
			url TEXT NOT NULL,
			latitude REAL NOT NULL,
			longitude REAL NOT NULL,
			location TEXT NOT NULL
		);

		CREATE TABLE IF NOT EXISTS data (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			timestamp INTEGER NOT NULL UNIQUE,
			download_speed INTEGER NOT NULL,
			upload_speed INTEGER NOT NULL,
			latency INTEGER NOT NULL,
			server_id INTEGER NOT NULL,
			FOREIGN KEY (server_id) REFERENCES server (id)
		);
	''')
	conn.commit()

	crsr.close()
	conn.close()


def get_speeds() -> speedtest.SpeedtestResults:
	logger.info('Obteniendo resultados de pruebas de velocidad')
	test = speedtest.Speedtest()
	test.download()
	test.upload()

	server = Server(
	    test.results.server['puerto'],
	    test.results.server['url'],
	    test.results.server['latitud'],
	    test.results.server['longitud'],
	    f"{test.results.server['nombre']}, {test.results.server['pais']}",
	)

	data = Data(
	    round(datetime.fromisoformat(test.results.timestamp[:-1]).timestamp()),
	    round(round(test.results.download / 1048576), 2),
	    round(round(test.results.upload / 1048576), 2),
	    round(test.results.ping),
	    server.id,
	)

	conn = sqlite3.connect(_db)
	crsr = conn.cursor()

	res = crsr.execute('SELECT id FROM server WHERE id = ?', (server.id, )).fetchone()
	if res is None:
		logger.info(f"Creando servidor:\n{pformat(server._asdict(), sort_dicts=False)}")
		crsr.execute('INSERT INTO server VALUES (?, ?, ?, ?, ?);', server)
		conn.commit()

	crsr.execute(
	    '''
		INSERT INTO data (timestamp, download_speed, upload_speed, latency, server_id)
		VALUES (?, ?, ?, ?, ?);
	''', data)
	conn.commit()

	crsr.close()
	conn.close()

	logger.info(f"Creando data:\n{pformat(data._asdict(), sort_dicts=False)}")
	return test.results


def run_schedule() -> NoReturn:
	get_speeds()

	logger.info('Horario de inicio')
	schedule.every().minute.at(':23').do(get_speeds)
	while True:
		schedule.run_pending()
		time.sleep(1)
