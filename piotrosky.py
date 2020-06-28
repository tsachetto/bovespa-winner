#!/usr/bin/env python3

# Para a análise, são utilizados princípios do Joseph D. Piotroski
# Estipulados no livro: "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers"
# No estudo original de Piotroski, ao longo de 20 anos (1976–1996), uma estratégia de investimento baseado nessa pontuação, com a compra de empresas com F-Score alto e a venda de empresas com F-Score baixo, gerou um retorno anual de 23%, bem superior à media do mercado.
# Piotroski elaborou um Scopre chamado "Piotroski F-score" que varia de 0 a 9, quanto maior, por mais filtros as ações passaram

import sys, os
sys.path.extend([f'./{name}' for name in os.listdir(".") if os.path.isdir(name)])

import fundamentus
import bovespa
import backtest

import pandas
import numpy

import http.cookiejar
import urllib.request
import json
import threading

def print(thing):
  import pprint
  return pprint.PrettyPrinter(indent=4).pprint(thing)

# Princípios utilizados:

# 1) ROA > 0 (ano corrente)
# 2) FCO > 0 (ano corrente)
# 3) FCO > Lucro Líquido (ano corrente)
# 4) ROA atual > ROA ano anterior
# 5) Alavancagem atual < ano passado (Dívida Líquida / Patrimônio Líquido)
# 6) Liquidez Corrente atual > Liquidez Corrente ano anterior
# 7) Nro. Ações atual = Nro. Ações ano anterior
# 8) Margem Bruta atual > Margem Bruta ano anterior
# 9) Giro Ativo atual > Giro Ativo ano anterior

def populate_shares(sys):
  year = None
  if len(sys.argv) > 1:
    arguments = eval(sys.argv[1])
    year = int(arguments['year'])
  
  globals()['year'] = year
  globals()['infos'] = {}
  
  if year == None:
    shares = bovespa.shares()
  else:
    shares = fundamentus.shares(year)
  
  shares = shares[shares['Cotação'] > 0]
  # shares = shares[shares['Liquidez 2 meses'] > 500]
  shares['Ranking'] = 0
  
  fill_infos(shares)
  
  shares = add_ratings(shares)
  
  shares = reorder_columns(shares)
  
  return shares

# infos = {
#   'TRPL4': {
#     'roa_positivo': True/False,
#     'fco_positivo': True/False,
#     'fco_saudavel': True/False,
#     'roa_crescente': True/False,
#     'alavancagem_decrescente': True/False,
#     'liquidez_crescente': True/False,
#     'no_acoes_constante': True/False,
#     'margem_bruta_crescente': True/False,
#     'giro_ativo_crescente': True/False
#   }
# }

def fill_infos(shares):
  cookie_jar = http.cookiejar.CookieJar()
  opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
  opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows; U; Windows NT 6.1; rv:2.2) Gecko/20110201'),
                       ('Accept', 'text/html, text/plain, text/css, text/sgml, */*;q=0.01')]
  tickets = list(shares.index)
  threads = [threading.Thread(target=fill_infos_by_ticket, args=(ticket,opener,)) for ticket in tickets]
  for thread in threads:
    thread.start()
  for thread in threads:
    thread.join()

def fill_infos_by_ticket(ticket, opener):
  infos[ticket] = {
    'roa_positivo': False,
    'fco_positivo': False,
    'fco_saudavel': False,
    'roa_crescente': False,
    'alavancagem_decrescente': False,
    'liquidez_crescente': False,
    'no_acoes_constante': False,
    'margem_bruta_crescente': False,
    'giro_ativo_crescente': False
  }
  
  # Fetching indicators
  current_indicators_url = f'https://api-analitica.sunoresearch.com.br/api/Indicator/GetIndicatorsDashboard?ticker={ticket}'
  with opener.open(current_indicators_url) as link:
    company_indicators = link.read().decode('ISO-8859-1')
  company_indicators = json.loads(company_indicators)

  yearly_indicators_url = f'https://api-analitica.sunoresearch.com.br/api/Indicator/GetIndicatorsYear?ticker={ticket}'
  with opener.open(yearly_indicators_url) as link:
    yearly_indicators = link.read().decode('ISO-8859-1')
  yearly_indicators = json.loads(yearly_indicators)
  
  company_indicators.extend(yearly_indicators)
  
  infos[ticket]['roa_positivo'] = company_indicators[0]['roa'] > 0
  infos[ticket]['fco_positivo'] = company_indicators[0]['fco'] > 0
  infos[ticket]['fco_saudavel'] = company_indicators[0]['fco'] > company_indicators[0]['lucroLiquido']
  infos[ticket]['roa_crescente'] = company_indicators[0]['roa'] > company_indicators[1]['roa']
  infos[ticket]['alavancagem_decrescente'] = company_indicators[0]['dlpl'] < company_indicators[1]['dlpl']
  infos[ticket]['liquidez_crescente'] = company_indicators[0]['liqCorrent'] > company_indicators[1]['liqCorrent']
  infos[ticket]['no_acoes_constante'] = company_indicators[0]['qntAcoes'] == company_indicators[1]['qntAcoes']
  infos[ticket]['margem_bruta_crescente'] = company_indicators[0]['margBruta'] > company_indicators[1]['margBruta']
  infos[ticket]['giro_ativo_crescente'] = company_indicators[0]['giroAtivos'] > company_indicators[1]['giroAtivos']

def add_ratings(shares):
  add_piotrosky_columns(shares)
  return fill_special_infos(shares)

# Inicializa os índices
def add_piotrosky_columns(shares):
  shares['Piotrosky Score'] = 0
  shares['ROA positivo'] = False
  shares['FCO positivo'] = False
  shares['FCO > Lucro Líquido'] = False
  shares['ROA crescente'] = False
  shares['Alavancagem decrescente'] = False
  shares['Liquidez Corrente crescente'] = False
  shares['No Ações constante'] = False
  shares['Margem Bruta crescente'] = False
  shares['Giro Ativo crescente'] = False

def fill_special_infos(shares):
  for index in range(len(shares)):
    ticker = shares.index[index]
    shares['Piotrosky Score'][index] += int(infos[ticker]['roa_positivo'])
    shares['ROA positivo'][index] = infos[ticker]['roa_positivo']
    shares['Piotrosky Score'][index] += int(infos[ticker]['fco_positivo'])
    shares['FCO positivo'][index] = infos[ticker]['fco_positivo']
    shares['Piotrosky Score'][index] += int(infos[ticker]['fco_saudavel'])
    shares['FCO > Lucro Líquido'][index] = infos[ticker]['fco_saudavel']
    shares['Piotrosky Score'][index] += int(infos[ticker]['roa_crescente'])
    shares['ROA crescente'][index] = infos[ticker]['roa_crescente']
    shares['Piotrosky Score'][index] += int(infos[ticker]['alavancagem_decrescente'])
    shares['Alavancagem decrescente'][index] = infos[ticker]['alavancagem_decrescente']
    shares['Piotrosky Score'][index] += int(infos[ticker]['liquidez_crescente'])
    shares['Liquidez Corrente crescente'][index] = infos[ticker]['liquidez_crescente']
    shares['Piotrosky Score'][index] += int(infos[ticker]['no_acoes_constante'])
    shares['No Ações constante'][index] = infos[ticker]['no_acoes_constante']
    shares['Piotrosky Score'][index] += int(infos[ticker]['margem_bruta_crescente'])
    shares['Margem Bruta crescente'][index] = infos[ticker]['margem_bruta_crescente']
    shares['Piotrosky Score'][index] += int(infos[ticker]['giro_ativo_crescente'])
    shares['Giro Ativo crescente'][index] = infos[ticker]['giro_ativo_crescente']
  return shares

# Reordena a tabela para mostrar a Cotação, o Valor Intríseco e o Graham Score como primeiras colunass
def reorder_columns(shares):
  columns = ['Ranking', 'Cotação', 'Piotrosky Score']
  return shares[columns + [col for col in shares.columns if col not in tuple(columns)]]

if __name__ == '__main__':
  from waitingbar import WaitingBar
  progress_bar = WaitingBar('[*] Calculating...')

  shares = populate_shares(sys)

  shares.sort_values(by=['Piotrosky Score', 'Cotação'], ascending=[False, True], inplace=True)

  shares['Ranking'] = range(1, len(shares) + 1)

  backtest.display_shares(shares, year)

  progress_bar.stop()

# https://api-analitica.sunoresearch.com.br/api/Indicator/GetIndicatorsYear?ticker=TRPL4
# https://api-analitica.sunoresearch.com.br/api/Indicator/GetIndicatorsDashboard?ticker=ITSA4


# "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers"