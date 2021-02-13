#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime as dt
import pdfplumber
from io import BytesIO
import unicodedata
import re

def get_reportfn():
    url = 'https://www.udape.gob.bo/index.php?option=com_content&view=article&id=220:reporte-covid-19&catid=41'
    html = BeautifulSoup(requests.get(url).text, 'html.parser')
    fn = html.select('#table1 li a')[0]['href'].split('/')[-1]
    return fn

def reportfn2date(fn):
    return dt.datetime.strptime(fn.split('COVID-2019_')[1], '%d_%m_%Y.pdf').date()

def get_last(fn):
    return pd.read_csv(fn, parse_dates=[0], index_col=0).index[-1].date()

def normie(text):
    return unicodedata.normalize(u'NFKD', ' '.join(text.lower().split())).encode('ascii', 'ignore').decode('utf8')

def is_diario(text):
    return len(re.findall('.*casos confirmados, fallecidos y recuperados por departamento por dia, del [0-9\/]*', text)) != 0

def is_acumulado(text):
    return len(re.findall('.*casos acumulados de confirmados, activos, fallecidos y recuperados por departamento, del [0-9\/]*', text)) != 0

def month_matcher(text):
    months = {'ago':8, 'oct':10, 'may':5, 'jul':7, 'sep':9, 'jun':6, 'nov':11, 'abr':4, 'dic':12, 'mar':3, 'ene':1, 'feb':2}
    return months[text]

def get_data_diarios(page):
    table = pd.DataFrame(page.extract_tables()[0]).T.drop(columns=[1])
    table.columns = table.iloc[0].apply(lambda _ : _.replace('(*)','').strip()).tolist()
    table = table[1:]
    confirmados_diarios_page, decesos_diarios_page, recuperados_diarios_page = [], [], []
    for i, row in table.iterrows():
        if row['Departamento'] != None:
            fecha = row['Departamento']
            ii = 0
            confirmados_diarios_page.append([fecha] + row[columns].tolist())
        else:
            if ii == 0:
                decesos_diarios_page.append([fecha] + row[columns].tolist())
                ii += 1
            else:
                recuperados_diarios_page.append([fecha] + row[columns].tolist())
    confirmados_diarios.extend(confirmados_diarios_page[::-1])
    decesos_diarios.extend(decesos_diarios_page[::-1])
    recuperados_diarios.extend(recuperados_diarios_page[::-1])

def get_data_acumulados(page):
    table = pd.DataFrame(page.extract_tables()[0]).T.drop(columns=[1])
    table.columns = table.iloc[0].apply(lambda _ : _.replace('(*)','').strip()).tolist()
    table = table[1:]
    confirmados_acumulados_page, activos_acumulados_page, decesos_acumulados_page, recuperados_acumulados_page = [], [], [], []
    for i, row in table.iterrows():
        if row['Departamento'] != None:
            fecha = row['Departamento']
            ii = 0
            confirmados_acumulados_page.append([fecha] + row[columns].tolist())
        else:
            if ii == 0:
                activos_acumulados_page.append([fecha] + row[columns].tolist())
                ii += 1
            elif ii == 1:
                decesos_acumulados_page.append([fecha] + row[columns].tolist())
                ii += 1
            else:
                recuperados_acumulados_page.append([fecha] + row[columns].tolist())
    confirmados_acumulados.extend(confirmados_acumulados_page[::-1])
    activos_acumulados.extend(activos_acumulados_page[::-1])
    decesos_acumulados.extend(decesos_acumulados_page[::-1])
    recuperados_acumulados.extend(recuperados_acumulados_page[::-1])
                
def format_date(text):
    global whatyear
    month = month_matcher(text.split('-')[1][:3])
    day = int(text.split('-')[0])
    if month == 1 and day == 1:
        whatyear += 1
    return dt.datetime(whatyear, month_matcher(text.split('-')[1][:3]), int(text.split('-')[0]))

def make_dataframe(data, filename):
    global whatyear
    data = data[::-1]
    whatyear = 2020
    df = pd.DataFrame(data, columns=['Fecha'] + columns)
    df = df.replace(to_replace='', value=0)
    df = df.replace(to_replace='\.', value='', regex=True)
    df.Fecha = df.Fecha.apply(lambda _: format_date(_))
    df.set_index('Fecha', inplace=True)
    df = pd.concat([empty, df], axis=0)
    df = df[~df.index.duplicated(keep='last')].fillna(0)
    df[columns] = df[columns].astype(int)
    df[df.index <= report_day].sort_index().to_csv(filename+'.csv')


# Nuevo reporte?
reportfn = get_reportfn()
last = get_last('confirmados_diarios.csv')
if last < reportfn2date(reportfn):

    report_day = reportfn2date(reportfn).strftime('%Y-%m-%d')
    report_url = 'https://www.udape.gob.bo/portales_html/ReporteCOVID/R_diario/' + reportfn
    columns = ['Chuquisaca', 'La Paz', 'Cochabamba', 'Oruro', 'Potosí', 'Tarija', 'Santa Cruz', 'Beni', 'Pando']
    empty = pd.DataFrame(index = pd.date_range('2020-03-10', report_day), columns=columns).fillna(0)
    whatyear = 2020

    # Cargo el reporte
    req = requests.get(report_url)
    if req.status_code != 200:
        raise SystemError("El enlace es incorrecto")
    try:
        pdf = pdfplumber.open(BytesIO(req.content))
    except Exception:
        raise SystemError("Error al cargar el pdf")

    # Donde acopio datos
    confirmados_diarios, decesos_diarios, recuperados_diarios = [],[],[]
    confirmados_acumulados, activos_acumulados, recuperados_acumulados, decesos_acumulados = [], [], [], []
    diario_pages, acumulado_pages = [], []

    # Una ojeada para encontrar las páginas que me interesan
    for i, page in enumerate(pdf.pages):
        pagetext = normie(page.extract_text())
        if is_diario(pagetext):
            diario_pages.append(page)
        if is_acumulado(pagetext):
            acumulado_pages.append(page)

    # procesar datos para casos diarios
    for page in diario_pages:
        get_data_diarios(page)

    make_dataframe(confirmados_diarios, 'confirmados_diarios')
    make_dataframe(decesos_diarios, 'decesos_diarios')
    make_dataframe(recuperados_diarios, 'recuperados_diarios')

    # procesar datos para casos acumulados
    for page in acumulado_pages:
        get_data_acumulados(page)
    
    make_dataframe(confirmados_acumulados, 'confirmados_acumulados')
    make_dataframe(activos_acumulados, 'activos_acumulados')
    make_dataframe(decesos_acumulados, 'decesos_acumulados')
    make_dataframe(recuperados_acumulados, 'recuperados_acumulados')

    print(report_day)
