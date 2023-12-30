import asyncio
import aiohttp
import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import Playwright, async_playwright

headers = {
    'sec-ch-ua': '"Chromium";v="118", "YaBrowser";v="23.11", "Not=A?Brand";v="99", "Yowser";v="2.5"',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://mirsud.spb.ru/',
    'X-Requested-With': 'XMLHttpRequest',
    'sec-ch-ua-mobile': '?0',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 YaBrowser/23.11.0.0 Safari/537.36',
    'sec-ch-ua-platform': '"Windows"',
}
async def get_table_data(browser, i: int):
    # Create a new page
    page = await browser.new_page()
    await page.goto(f'https://mos-sud.ru/{i}')
    rows = await page.query_selector_all('tr[data-v-4f8a0cf2=""]')

    data = {'Номер': i}
    for row in rows:
        # Находим все ячейки в строке
        cells = await row.query_selector_all('td[data-v-4f8a0cf2=""]')
        if len(cells) == 2:
            # Извлекаем текст из ячеек
            key = await cells[0].text_content()
            value = await cells[1].text_content()
            
            data[key] = value
    await page.close()
    return data


async def get_moscow_court_data(playwright: Playwright) -> None:
    df_moscow = pd.DataFrame()
    # Launch a new browser instance
    context = await playwright.chromium.launch_persistent_context(
        headless=False,
        user_data_dir='/user_data/'
    )
    data = []
    tasks = []
    for i in range(1, 471):
        tasks.append(get_table_data(context, i))
        if len(tasks) == 10:
            data.extend(await asyncio.gather(*tasks))
            tasks = []
    if tasks:
        data.extend(await asyncio.gather(*tasks))
    for row in data:
        df_moscow = df_moscow._append(row, ignore_index=True)
    # Close the browser
    await context.close()
    
    return df_moscow

async def get_spb_court_data(session: aiohttp.ClientSession):
    df_spb = pd.DataFrame()

    response_json = await session.get('https://mirsud.spb.ru/court-sites/json/', headers=headers)
    response_json = await response_json.json()
    courts_data = []
    
    for item in response_json['data']:
        courts_data.append(('https://mirsud.spb.ru'+item['url'], item['court_number']))
    
    for url, court_number in courts_data:
        async with session.get(url, headers=headers) as response:
            try:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')

                address = soup.find('div', class_='adress-fact').find('p').text.strip()
                phone = soup.find('div', class_='telfax').find('p').text.strip()
                reseption = soup.find('div', class_='reseption').find('p').text.replace('\n', '').strip()
                open_time = soup.find('div', class_='open-hours').find('td').text.strip()
                email = soup.find('a', class_='link__mail').text.strip()
                judge_element = soup.find('b', string='Судья')
                if judge_element:
                    judge_name = judge_element.find_next('p').text.strip()
                else:
                    print("Информация о судье не найдена.")
                
                region_element = soup.find('b', string='Район')
                if region_element:
                    region_name = region_element.find_next('p').text.strip()
                else:
                    print("Информация о судье не найдена.")

                df_spb = df_spb._append({'№': court_number, 'Адрес фактический': address, 'Телефон/факс': phone, 'Приём граждан': reseption, 'Часы работы': open_time, 'E-mail': email, "Судья": judge_name, 'Район': region_name, 'Ссылка': url}, ignore_index=True)
            except Exception as ex:
                print(ex, url)


    return df_spb

async def main():
    async with aiohttp.ClientSession() as session:
        # Запускаем асинхронные задачи
        async with async_playwright() as playwright:
            df_spb = await get_spb_court_data(session)
            # df_moscow = await get_moscow_court_data(playwright)

    # Сохраняем результаты в файлы Excel
    df_spb.to_excel('spb_courts.xlsx', index=False)
    # df_moscow.to_excel('moscow_courts.xlsx', index=False)

if __name__ == '__main__':
    asyncio.run(main())
