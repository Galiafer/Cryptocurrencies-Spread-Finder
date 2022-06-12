import json
from selenium import webdriver
import requests
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
import re
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from webdriver_manager.chrome import ChromeDriverManager

config = json.load(open("config.json"))

MIN_SPREAD = config['minSpread']
MAX_SPREAD = config['maxSpread']
ALLOWED_QUOTES = config['allowedQuotes']
MIN_TRADING_VOLUME = config['minTradingVolume']
MAX_TRADING_VOLUME = config['maxTradingVolume']
START_RANK_POSITION = config['startRankPosition']


def getDriver() -> webdriver:
    options = Options()
    options.add_argument("--disable-gpu")
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(
        executable_path=ChromeDriverManager().install(), options=options)

    return driver


def loadAllCryptocurrencies(driver) -> None:
    driver.get("https://cryptorank.io/performance")

    WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((By.XPATH, '//*[@id="__next"]/div/div[1]/div[3]/div['
                                                  '2]/div[3]/div[3]/div[2]/a[8]')))

    driver.find_element(By.XPATH, '//*[@id="__next"]/div/div[1]/div[3]/div[2]/div[3]/div[3]/div[2]/a[8]').click()

    WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((By.XPATH, '//*[@id="__next"]/div/div[1]/div[3]/div['
                                                  '2]/div[3]/div[4]/button')))

    driver.find_element(By.XPATH,
                        '//*[@id="__next"]/div/div[1]/div[3]/div[2]/div[3]/div[1]/div[1]/div[2]/button').click()

    WebDriverWait(driver, 120).until(EC.presence_of_element_located(
        (By.XPATH, '//*[@id="side-filter-root"]/div/div[1]/div[1]/div[4]/div[5]/div[1]/div[2]/div[1]/input')))
    driver.find_element(By.XPATH,
                        '//*[@id="side-filter-root"]/div/div[1]/div[1]/div[4]/div[5]/div[1]/div[2]/div[1]/input').send_keys(
        MIN_TRADING_VOLUME)
    driver.find_element(By.XPATH,
                        '//*[@id="side-filter-root"]/div/div[1]/div[1]/div[4]/div[5]/div[1]/div[2]/div[2]/input').send_keys(
        MAX_TRADING_VOLUME)
    driver.find_element(By.XPATH,
                        '//*[@id="side-filter-root"]/div/div[1]/div[1]/div[4]/div[1]/div/div[2]/div[1]/input').send_keys(
        START_RANK_POSITION)
    driver.find_element(By.XPATH, '//*[@id="side-filter-root"]/div/div[1]/div[2]/button[3]').click()

    while EC.presence_of_element_located((By.XPATH, '//*[@id="__next"]/div/div[1]/div[3]/div['
                                                    '2]/div[3]/div[4]/button')):
        try:
            driver.find_element(By.XPATH, '//*[@id="__next"]/div/div[1]/div[3]/div['
                                          '2]/div[3]/div[4]/button').click()
        except NoSuchElementException:
            break


def getAllLinks(driver) -> list:
    links = list()
    for href in driver.find_elements(By.CSS_SELECTOR, "#__next > div > div.layout__MainAppContent-sc-65duwd-1.ghnVnX > "
                                                      "div.container__Container-sc-1lptxhk-0.dSmiAf > div.page-content > "
                                                      "div.data-table.data-tables__StyledDataTable-sc-1s3eqid-0.jKqGpi > "
                                                      "div.data-table__table-wrapper > div > table > tbody > tr > "
                                                      "td.left.aligned.nametd > div > a"):
        links.append(f"{href.get_attribute('href')}/arbitrage")

    return links


def getData(links) -> list:
    data = list()

    for link in links:
        coin = re.split('https://cryptorank\.io/price/|/arbitrage', link)[1]
        response = requests.get(f'https://api.cryptorank.io/v0/coins/{coin}/tickers?includeQuote=false').json()

        allowedData = []
        exchanges = list()
        for i in range(len(response['data'])):
            if len(response['data']) > 1 and response['data'][i]['to'] in ALLOWED_QUOTES:
                if "usdVolume" in response['data'][i] and response['data'][i]["usdVolume"] > MIN_TRADING_VOLUME:
                    if "usdLast" in response['data'][i]:
                        allowedData.append(response['data'][i])
                        exchanges.append({
                            'exchange_name': response['data'][i]['exchangeName'],
                            "volume": response['data'][i]['usdVolume'],
                            "usd_last": response['data'][i]['usdLast'],
                        })
        pairs = list()
        for i in range(len(allowedData)):
            for j in range(len(allowedData)):
                if i == j:
                    continue

                firstExchange = allowedData[i]
                secondExchange = allowedData[j]

                spread = 100 * (float(firstExchange['usdLast']) - float(secondExchange['usdLast'])) / float(
                    firstExchange['usdLast'])
                if MIN_SPREAD <= spread <= MAX_SPREAD:
                    coinName = allowedData[0]['coinName']
                    pairs.append({
                        secondExchange['exchangeName']: secondExchange['url'],
                        firstExchange['exchangeName']: firstExchange['url'],
                        "scheme": f"{secondExchange['exchangeName']} [BUY] -> {firstExchange['exchangeName']} [SELL]",
                        "spread": spread
                    })

        if len(exchanges) > 0 and len(pairs) > 0:
            scheme = {
                "name": coin,
                "url": f'https://cryptorank.io/price/{coin}',
                "exchanges": list(exchanges),
                "pairs": list(pairs)
            }
            data.append(scheme)

    return data


driver = getDriver()

loadAllCryptocurrencies(driver)

links = getAllLinks(driver)
print(f"Input Data: {len(links)}")

driver.close()

data = getData(links)

with open('data.json', 'w', encoding='utf-8') as f:
    print(f"Output Data: {len(data)}")
    json_data = {"data": data}
    json.dump(json_data, f, ensure_ascii=False, indent=4)
