#!/usr/bin/env python
# coding: utf-8

# In[39]:


from flask import Flask, jsonify
import requests
import pandas as pd
from io import StringIO, BytesIO
from requests.auth import HTTPBasicAuth
from fuzzywuzzy import fuzz, process
import pdfplumber
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
import os

app = Flask(__name__)

# Configuration
CONFLUENCE_BASE_URL = "https://englebertltd.atlassian.net/wiki"
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")
CONFLUENCE_USER_EMAIL = "nikolas@englebert.xyz"
PAGE_ID = "86671364"

# Fetch data from Confluence
@app.route('/sanctions_check', methods=['GET'])
def sanctions_check():
    try:
        # Fetch the table from Confluence
        confluence_data = get_confluence_table(PAGE_ID)
        
        # Process fetched data
        businesses = process_business_data(confluence_data)
        
        # Fetch and compare sanctions lists
        sanctions_results = run_sanctions_check(businesses)
        
        return jsonify(sanctions_results)
    except Exception as e:
        return jsonify({"error": str(e)})

# Function to fetch data from Confluence
def get_confluence_table(page_id):
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}?expand=body.storage"
    response = requests.get(url, auth=HTTPBasicAuth(CONFLUENCE_USER_EMAIL, CONFLUENCE_API_TOKEN))
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from Confluence: {response.status_code}")
    
    data = response.json()
    html_table = data['body']['storage']['value']
    df = pd.read_html(StringIO(html_table))[0]
    
    return df

def process_business_data(table_df):
    businesses = []
    token_issuers = table_df.iloc[0]['Token Issuer'].split(', ')
    key_individuals = table_df.iloc[0]['Key Individuals'].split(', ')

    for issuer in token_issuers:
        businesses.append({
            'issuer': issuer,
            'key_individuals': key_individuals
        })
    
    return businesses

# Helper function to handle in-memory downloads
def download_file_to_memory(url):
    response = requests.get(url)
    return BytesIO(response.content)

# Helper functions for Selenium
def fetch_html_content_with_selenium(url):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    chromedriver_path = '/Users/nikolasspence/Library/CloudStorage/OneDrive-EnglebertLimited/Python_Files/chromedriver'  # Update this path
    driver = webdriver.Chrome(service=ChromeService(chromedriver_path), options=options)
    
    driver.get(url)
    html_content = driver.page_source
    driver.quit()
    
    return html_content

def find_dynamic_url_with_selenium(main_page_url):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    chromedriver_path = '/Users/nikolasspence/Library/CloudStorage/OneDrive-EnglebertLimited/Python_Files/chromedriver'
    driver = webdriver.Chrome(service=ChromeService(chromedriver_path), options=options)
    
    driver.get(main_page_url)
    dynamic_url = None
    a_tags = driver.find_elements(By.TAG_NAME, 'a')
    for a_tag in a_tags:
        href = a_tag.get_attribute('href')
        if href and "en-all.html" in href:
            dynamic_url = href
            break
    
    driver.quit()
    return dynamic_url

# Extract text from PDF
def extract_text_from_pdf(pdf_data):
    text = ""
    with pdfplumber.open(pdf_data) as pdf:
        for page in pdf.pages:
            text += page.extract_text()
    return text

#Fetch HTML data
def fetch_html_data(url):
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from {url}: {response.status_code}")
    # Parse the HTML using BeautifulSoup
    soup = BeautifulSoup(response.content, 'html.parser')
    return soup


# Extract names from OFAC CSV
def extract_names_from_ofac_csv(csv_data):
    df = pd.read_csv(csv_data, header=None)
    return df.iloc[:, 1].tolist()  # Adjust to use the second column for names

# Extract names from EU text
def extract_names_from_eu_text(eu_text):
    names = []
    name_pattern = re.compile(r'• Name(?:/Alias)?:\s*([\w\s,\']+)(?:\n|Title|Function|Birth|$)', re.IGNORECASE)
    for match in name_pattern.findall(eu_text):
        names.append(match.strip().replace('\n', ' ').strip())
    return names

def extract_names_from_uk_text(uk_text):
    names = []
    # Regular expression to extract names from the UK sanctions list
    name_pattern = re.compile(r'Name: ([\w\s,\'-]+)(?= Name Type:|$)', re.IGNORECASE)
    for match in name_pattern.findall(uk_text):
        names.append(match.strip())
    return names

# Extract names from UN HTML
def extract_names_from_un_html(un_html):
    soup = BeautifulSoup(un_html, 'html.parser')
    names = []
    for row in soup.find_all('tr', class_='rowtext'):
        strong_tags = row.find_all('strong')
        for strong_tag in strong_tags:
            if 'Name:' in strong_tag.text:
                name_text = strong_tag.next_sibling
                name_parts = re.split(r'\d+:\s*|\s*na\s*|\s+', name_text)
                filtered_parts = [part for part in name_parts if part and not part.isdigit() and part.lower() != 'na']
                name = " ".join(filtered_parts)
                names.append(name)
    return names

# Fetch and process sanctions lists
def run_sanctions_check(businesses):
    ofac_url = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"
    ofac_csv_data = download_file_to_memory(ofac_url)
    ofac_names = extract_names_from_ofac_csv(ofac_csv_data)

    eu_names = fetch_eu_list()
    uk_names = fetch_uk_list()
    un_names = fetch_un_list()

    ofac_matches = fuzzy_match_names(businesses, ofac_names)
    eu_matches = fuzzy_match_names(businesses, eu_names)
    uk_matches = fuzzy_match_names(businesses, uk_names)
    un_matches = fuzzy_match_names(businesses, un_names)
    
    return {
        "OFAC Matches": ofac_matches,
        "EU Matches": eu_matches,
        "UK Matches": uk_matches,
        "UN Matches": un_matches
    }

# Fetch EU, UK, and UN lists
def fetch_eu_list():
    eu_url = "https://webgate.ec.europa.eu/fsd/fsf/public/files/pdfFullSanctionsList/content?token=dG9rZW4tMjAxNw"
    pdf_data = download_file_to_memory(eu_url)
    eu_text = extract_text_from_pdf(pdf_data)
    return extract_names_from_eu_text(eu_text)

def fetch_uk_list():
    uk_url = "https://docs.fcdo.gov.uk/docs/UK-Sanctions-List.html"
    
    # Fetch the HTML from the UK Sanctions List
    soup = fetch_html_data(uk_url)  # Ensure this returns a BeautifulSoup object
    
    # Extract the text from the parsed HTML
    uk_data = soup.get_text()  # Extracts the entire text content from the page
    
    # Extract names from the UK sanctions list text
    return extract_names_from_uk_text(uk_data)


def fetch_un_list():
    un_main_url = "https://scsanctions.un.org/consolidated"
    un_dynamic_url = find_dynamic_url_with_selenium(un_main_url)
    if un_dynamic_url:
        un_html = fetch_html_content_with_selenium(un_dynamic_url)
        return extract_names_from_un_html(un_html)
    return []

# String matching
def fuzzy_match_names(businesses, sanctions_names, threshold=85):
    matches = []
    for business in businesses:
        issuer = business['issuer']
        match = process.extractOne(issuer, sanctions_names, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= threshold:
            matches.append((issuer, match[0], match[1]))

        for individual in business['key_individuals']:
            match = process.extractOne(individual, sanctions_names, scorer=fuzz.token_sort_ratio)
            if match and match[1] >= threshold:
                matches.append((individual, match[0], match[1]))
    
    return matches

if __name__ == '__main__':
    app.run(debug=True)


# In[49]:


get_ipython().system('jupyter nbconvert --to script InstantSanctionsScan_Flask.ipynb')


# In[ ]:




