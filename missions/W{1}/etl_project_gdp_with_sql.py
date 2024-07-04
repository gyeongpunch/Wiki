import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# 로그 기록 함수
def log(message): # log message를 etl_project_log.txt 파일에 기록
    log_path = '/Users/admin/Desktop/Data_Engineering/W1/ETL/etl_project_log.txt' # txt 파일 위치
    with open(log_path, 'a') as f:
        current_time = datetime.now().strftime('%Y-%b-%d-%H-%M-%S')
        f.write(f"{current_time}, {message}\n") # 현재 날짜 및 시간, message를 write

# 대륙별 국가 목록
continent_countries = {
    "Asia": ["Afghanistan", "Armenia", "Azerbaijan", "Bahrain", "Bangladesh", "Bhutan", "Brunei", "Cambodia", "China", "Cyprus", "Georgia", "India", "Indonesia", "Iran", "Iraq", "Israel", "Japan", "Jordan", "Kazakhstan", "Kuwait", "Kyrgyzstan", "Laos", "Lebanon", "Malaysia", "Maldives", "Mongolia", "Myanmar", "Nepal", "North Korea", "Oman", "Pakistan", "Palestine", "Philippines", "Qatar", "Saudi Arabia", "Singapore", "South Korea", "Sri Lanka", "Syria", "Taiwan", "Tajikistan", "Thailand", "Timor-Leste", "Turkey", "Turkmenistan", "United Arab Emirates", "Uzbekistan", "Vietnam", "Yemen"],
    "North America": ["Antigua and Barbuda", "Bahamas", "Barbados", "Belize", "Canada", "Costa Rica", "Cuba", "Dominica", "Dominican Republic", "El Salvador", "Grenada", "Guatemala", "Haiti", "Honduras", "Jamaica", "Mexico", "Nicaragua", "Panama", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Trinidad and Tobago", "United States"],
    "Europe": ["Albania", "Andorra", "Armenia", "Austria", "Azerbaijan", "Belarus", "Belgium", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Denmark", "Estonia", "Finland", "France", "Georgia", "Germany", "Greece", "Hungary", "Iceland", "Ireland", "Italy", "Kazakhstan", "Kosovo", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Malta", "Moldova", "Monaco", "Montenegro", "Netherlands", "North Macedonia", "Norway", "Poland", "Portugal", "Romania", "Russia", "San Marino", "Serbia", "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland", "Turkey", "Ukraine", "United Kingdom", "Vatican City"],
    "South America": ["Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador", "Guyana", "Paraguay", "Peru", "Suriname", "Uruguay", "Venezuela"],
    "Africa": ["Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi", "Cabo Verde", "Cameroon", "Central African Republic", "Chad", "Comoros", "Congo", "Djibouti", "Egypt", "Equatorial Guinea", "Eritrea", "Eswatini", "Ethiopia", "Gabon", "Gambia", "Ghana", "Guinea", "Guinea-Bissau", "Ivory Coast", "Kenya", "Lesotho", "Liberia", "Libya", "Madagascar", "Malawi", "Mali", "Mauritania", "Mauritius", "Morocco", "Mozambique", "Namibia", "Niger", "Nigeria", "Rwanda", "Sao Tome and Principe", "Senegal", "Seychelles", "Sierra Leone", "Somalia", "South Africa", "South Sudan", "Sudan", "Tanzania", "Togo", "Tunisia", "Uganda", "Zambia", "Zimbabwe"],
    "Oceania": ["Australia", "Fiji", "Kiribati", "Marshall Islands", "Micronesia", "Nauru", "New Zealand", "Palau", "Papua New Guinea", "Samoa", "Solomon Islands", "Tonga", "Tuvalu", "Vanuatu"]
}

def extract_data(url): # url에서 Data를 extraction
    log("Data extraction started") # Extract log 기록
    tables = pd.read_html(url, match='Forecast') # 해당 url에서 가져올 table 설정
    df = tables[0] # Table을 DataFrame에 담는다.
    log("Data extraction completed")
    return df

def transform_data(df): # Data 전처리 및 변환
    log("Data transformation started") # Transform log 기록
    df.columns = df.columns.to_flat_index() # 이중 index 처리
    df.columns = ['_'.join(col) for col in df.columns]
    df = df.drop(columns=[  # 필요없는 column Drop
        'IMF[1][13]_Year',
        'World Bank[14]_Estimate',
        'World Bank[14]_Year',
        'United Nations[15]_Estimate',
        'United Nations[15]_Year'
    ])
    df = df[1:].reset_index(drop=True) # World 누적 GDP 제외
    # DataFrame의 GDP 중 IMF가 측정하지 못한 GDP를 Nan으로 처리
    df['IMF[1][13]_Forecast'] = pd.to_numeric(df['IMF[1][13]_Forecast'].replace({'—': None, ',': ''}, regex=True), errors='coerce')
    
    # 현재 날짜와 시간 추가 (맨 앞에 컬럼으로 삽입)
    df.insert(0, 'Date', datetime.now().strftime("%Y-%b-%d-%H-%M-%S"))
    
    # column name 변경
    df = df.rename(columns={'Country/Territory_Country/Territory': 'Country', 'IMF[1][13]_Forecast': 'GDP_USD_billion'})
    
    # 대륙 컬럼 추가
    df['Continent'] = df['Country'].map(lambda x: next((continent for continent, countries in continent_countries.items() if x in countries), 'Other'))
    
    # Billion 단위로 변경
    df['GDP_USD_billion'] = (df['GDP_USD_billion'] / 1000).round(2)
    log("Data transformation completed")
    return df

def load_data(df, db_path): # Data를 DB에 Load
    log("Data load started") # Load log 기록
    
    # SQLite에 연결
    conn = sqlite3.connect(db_path)
    
    # 전체 데이터(Total_Countries_by_GDP) 저장
    df.to_sql('Total_Countries_by_GDP', conn, if_exists='replace', index=False)
    
    # 100B GDP를 넘는 국가만(OVER_100B_Countries_by_GDP) 저장
    df_over_100b = df[df['GDP_USD_billion'] > 100]
    df_over_100b.to_sql('OVER_100B_Countries_by_GDP', conn, if_exists='replace', index=False)
    
    # 100B USD이상인 GDP 국가 출력
    print(f"OVER 100B USD GDP countries:")
    print(df_over_100b, end = '\n\n')
    
    # 100B GDP 국가를 JSON 파일로 저장
    json_path = f"/Users/admin/Desktop/Data_Engineering/W1/ETL/World_GDP/Countries_by_GDP_{datetime.now().strftime('%Y-%b-%d-%H-%M')}.json"
    df_over_100b.to_json(json_path, orient='records', lines=True)
    
    # 대륙별 TOP 5 GDP 국가 저장 및 출력
    for continent in continent_countries.keys():
        df_continent = df[df['Continent'] == continent] # DataFrame을 도는데 상위 5개의 GDP 국가를 'TOP_5_Continent' table에 저장
        df_top5 = df_continent.nlargest(5, 'GDP_USD_billion')
        table_name = f'TOP5_GDP_{continent.replace(" ", "_")}'
        
        # 테이블 생성 및 데이터 삽입
        df_top5.to_sql(table_name, conn, if_exists='replace', index=False)
        
        # 대륙별 상위 5개 국가 출력
        print(f"Top 5 GDP countries in {continent}:")
        print(df_top5)
        print(f'{continent}의 TOP5 평균 GDP는 {(df_top5['GDP_USD_billion'].sum() / 5).round(2)} 입니다.', end = '\n\n')
    
    conn.commit()
    conn.close()
    log("Data load completed")

def etl_process():
    """ETL 프로세스를 실행한다."""
    log("ETL process started")
    url = 'https://en.wikipedia.org/wiki/List_of_countries_by_GDP_%28nominal%29'
    df = extract_data(url) # Extract process 실행
    df = transform_data(df) # Transform process 실행
    db_path = f"/Users/admin/Desktop/Data_Engineering/W1/ETL/World_GDP/World_Economies_{datetime.now().strftime('%Y-%b-%d-%H-%M')}.db"
    
    # 디렉토리가 존재하지 않는 경우 생성
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    load_data(df, db_path) # Load process 실행
    log("ETL process completed")

def wait_until_next_hour(): # 지금은 정각마다 DB에 저장하는 코드를 작성했다.
                            # 정각마다 DB에 잘 저장하는 것을 확인했으므로 주기를 분기 또는 반기 단위로 하여 GDP를 update하면 된다.
    now = datetime.now()
    # 다음 정각 계산
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    
    # 다음 정각까지의 시간을 계산하여 불필요한 Overhead가 발생하지 않게 sleep하도록 하였다.
    wait_seconds = (next_hour - now).total_seconds()
    time.sleep(wait_seconds)

if __name__ == "__main__":
    # ETL 프로세스를 첫 실행
    etl_process()
    # 정각마다 ETL 프로세스를 실행
    while True:
        wait_until_next_hour() # 다음 정각을 계산하고 남는 시간만큼 sleep한다.
        etl_process() # ETL process를 진행한다.
