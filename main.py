import requests
from lxml import etree
import re
import pprint


def get_missing_credits(session):
    award_entries_response = session.get('https://lotw.arrl.org/lotwuser/accountcredits?awg_id=DXCC&ac_acct=1&ac_view'
                                         '=alle&aw_id=DXCC-40&ac_order=1')
    parsed_page = etree.HTML(award_entries_response.text)
    table = parsed_page.xpath("//table[@id='creditsTable']//tbody")
    return {key.strip(): child.getchildren()[0].text.split('-')[1].strip()
            for child in table[0].getchildren()
                if child.getchildren()[1].text is not None
                and '-' in child.getchildren()[0].text
                and '(DELETED)' not in child.getchildren()[0].text
            for key in child.getchildren()[0].text.split('-')[0].strip().split(',')}


def get_call_sign_data(qrz_session, call_sign):
    data_response = requests.post('http://www.arrl.org/advanced-call-sign-search',
                                  data={'data[Search][terms]': call_sign})
    parsed_page = etree.HTML(data_response.text)
    data_block = parsed_page.xpath("//div[@class='list2']//ul//li")
    name = ''
    address = ''
    if data_block:
        name = ','.join(data_block[0].getchildren()[0].text.split(',')[:-1]).strip()
        address = ', '.join([c.strip() for c in data_block[0].getchildren()[1].itertext()][:2])
    if not name or not address:  # This is to limit the calls to qrz since they have a daily call limit.
        qrz_page_response = qrz_session.post('https://www.qrz.com/db',
                                             data={'query': call_sign, 'cs': call_sign, 'sel': None, 'cmd': 'Search',
                                                   'mode': 'callsign'})
        qrz_parsed_page = etree.HTML(qrz_page_response.text)
        qrz_data_block = qrz_parsed_page.xpath("//p[@class='m0']")
        if qrz_data_block:
            content = [c.strip() for c in qrz_data_block[0].itertext()]
            name = content[0]
            address = ', '.join(content[2:])
    return {key: value for key, value in {'name': name, 'address': address, 'call_sign': call_sign}.items() if value}


def get_contacted_call_signs(session):
    qso_response = session.get('https://lotw.arrl.org/lotwuser/lotwreport.adi?qso_query=1&qso_withown=yes'
                               '&qso_qslsince=1900-01-01', stream=True)
    qso_text = ''.join([content.decode('utf-8') for content in qso_response.iter_content(chunk_size=1024)])
    return re.findall('^[<]CALL:[0-9][>](?P<call_sign>.*?)\r$', qso_text, flags=re.MULTILINE)


def main(session, qrz_session, own_call_sign, arrl_pass, qrz_pass):
    session.post('https://lotw.arrl.org/lotwuser/login',
                 data='login=%s&password=%s&acct_sel=&thisForm=login' % (own_call_sign, arrl_pass))

    qrz_session.post('https://www.qrz.com/login', data={'username': own_call_sign, 'password': qrz_pass})

    missing_credits = get_missing_credits(session)
    call_signs = get_contacted_call_signs(session)
    call_sign_to_country = {country: [get_call_sign_data(qrz_session, call_sign) for call_sign in
                                      filter(lambda call_sign: call_sign.startswith(prefix), call_signs)] for
                            prefix, country in missing_credits.items()}
    return {key: value for key, value in call_sign_to_country.items() if value}


if __name__ == "__main__":
    pprint.pprint(main(session=requests.session(), qrz_session=requests.session(), own_call_sign=input('Enter your Call Sign: '),
                       arrl_pass=input('Enter your ARRL Password: '), qrz_pass=input('Enter your QRZ Password: ')))

# QRZ API CODE
# Note: Does not get address without subscription
# qrz_session_response = requests.get('http://xmldata.qrz.com/xml/current/?username=%s;password=%s' % (own_call_sign, qrz_pass))
# qrz_session_data = etree.fromstring(qrz_session_response.content)
# session_key = qrz_session_data.find('.//{http://xmldata.qrz.com}Key').text
# qrz_call_sign_data_response = requests.get('http://xmldata.qrz.com/xml/current/?s=%s;callsign=%s' % (session_key, call_sign))
# qrz_call_sign_data = etree.fromstring(qrz_call_sign_data_response.content)

# print(qrz_call_sign_data_response.content)
# if qrz_call_sign_data:
#     name2 = ' '.join([qrz_call_sign_data.find('.//{http://xmldata.qrz.com}fname').text, qrz_call_sign_data.find('.//{http://xmldata.qrz.com}name').text])
#     address2 = ', '.join([qrz_call_sign_data.find('.//{http://xmldata.qrz.com}%s' % key).text for key in ['addr1', 'addr2', 'state', 'zip', 'country'] if qrz_call_sign_data.find('.//{http://xmldata.qrz.com}%s' % key) is not None ])
