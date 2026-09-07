"""Collect public KOMIS chart responses without mixing price standards."""
import asyncio
import math
import sqlite3
from datetime import datetime, timezone
from threading import Lock
import requests
from backend.config import ROOT_DIR

SOURCE = 'https://www.komis.or.kr'
POLL_SECONDS = 3600
MATERIALS = [('lithium','리튬','MNRL0001'), ('nickel','니켈','MNRL0002'), ('cobalt','코발트','MNRL0003'), ('manganese','망간','MNRL0004')]
_lock = Lock()
_error = None
_checked_at = None
_collecting = False

def database():
    path = ROOT_DIR / 'data' / 'material_prices.db'
    path.parent.mkdir(exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    # SMM historical observations remain separate: currencies and grades differ.
    db.execute('CREATE TABLE IF NOT EXISTS komis_prices (material TEXT, standard TEXT, unit TEXT, date TEXT, price REAL, collected TEXT, PRIMARY KEY(material,standard,unit,date))')
    return db

def parse_chart(payload, code):
    data = payload.get('data') or {}
    info = data.get('mnrlInfo') or {}
    unit, weight = info.get('prcUnitCdNm'), info.get('weigUnitCd')
    standard = data.get('prcCrtr')
    series = [s for s in data.get('series', []) if s.get('spid') == code]
    dates = data.get('xaxis', [])
    if not unit or not weight or not standard or len(series) != 1:
        raise ValueError('Missing price standard or unit')
    values = series[0].get('data', [])
    if len(dates) != len(values):
        raise ValueError('Mismatched chart dimensions')
    points = {}
    for date, value in zip(dates, values):
        if value in (None, '', '-'):
            continue
        date = datetime.strptime(date, '%Y.%m.%d').date().isoformat()
        price = float(str(value).replace(',', ''))
        if not math.isfinite(price) or price <= 0:
            raise ValueError('Invalid quote')
        points[date] = price
    if not points:
        raise ValueError('Empty public chart')
    return standard, f'{unit}/{weight}', sorted(points.items())

def collect_prices():
    global _error, _checked_at, _collecting
    if not _lock.acquire(blocking=False):
        return
    _collecting = True
    failed = []
    try:
        with requests.Session() as session, database() as db:
            session.headers.update({'User-Agent':'FUTURE-M-RADAR/2.1', 'Referer':SOURCE+'/'})
            for key, name, code in MATERIALS:
                if not code:
                    continue
                try:
                    response = session.post(SOURCE+'/Komis/RsrcPrice/ajax/getMainChartData', data={'mnrkndUnqCd':code}, timeout=(5,15))
                    response.raise_for_status()
                    standard, unit, points = parse_chart(response.json(), code)
                    collected = datetime.now(timezone.utc).isoformat()
                    db.executemany('INSERT OR REPLACE INTO komis_prices VALUES (?,?,?,?,?,?)', [(key,standard,unit,date,price,collected) for date,price in points])
                    db.commit()
                except (requests.RequestException, ValueError, TypeError, KeyError):
                    failed.append(name)
        _error = ('KOMIS 조회 실패: '+', '.join(failed)+' · 저장된 가격은 기준일을 확인하세요.') if failed else None
    except Exception:
        _error = 'KOMIS 수집 오류 · 기존 저장 데이터는 유지됩니다.'
    finally:
        _checked_at = datetime.now(timezone.utc).isoformat()
        _collecting = False
        _lock.release()

async def material_monitor_loop():
    while True:
        await asyncio.to_thread(collect_prices)
        await asyncio.sleep(POLL_SECONDS)

def material_prices():
    items = []
    with database() as db:
        for key, name, code in MATERIALS:
            latest = db.execute('SELECT standard,unit FROM komis_prices WHERE material=? ORDER BY collected DESC,date DESC LIMIT 1', (key,)).fetchone()
            standard, unit = latest if latest else ('공개 가격 미연결', '')
            history = db.execute('SELECT date,price,collected FROM komis_prices WHERE material=? AND standard=? AND unit=? ORDER BY date DESC LIMIT 1000', (key,standard,unit)).fetchall()[::-1]
            last = history[-1] if history else None
            previous = history[-2][1] if len(history)>1 else None
            items.append(dict(id=key,name=name,grade=standard,code=code,unit=unit,source=SOURCE,
                price=last[1] if last else None,
                change_pct=round((last[1]/previous-1)*100,2) if previous else None,
                date=last[0] if last else None,collected_at=last[2] if last else None,
                history=[dict(date=r[0],price=r[1]) for r in history],status='available' if last else 'unavailable'))
    return dict(items=items,error=_error,checked_at=_checked_at,collecting=_collecting,refresh_seconds=POLL_SECONDS)
