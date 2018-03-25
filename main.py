__author__ = "Nicholas Logan"
__copyright__ = "Copyright 2018, Nicholas Logan"
__credits__ = ["Nicholas Logan", "Igor Dorovskoy"]
__license__ = "GNU GPL3"
__version__ = "0.2.0"
__maintainer__ = "Nicholas Logan"
__email__ = "nicholasklogan@gmail.com"
__status__ = "Prototype"
import requests
from lxml import etree
import re
import pprint
from functional import chain, concurrently, to, split_to, map, filterer, zipper, curry

start_session = requests.session
filter_empty_values = to(filterer(func=lambda item: item[1], kw='item'), kw='iterable')
format_arrl_login_data = 'login={}&password={}&acct_sel=&thisForm=login'.format
format_qrz_login_data = to(chain(zipper(iter1=('username', 'password')), dict), kw='iter2')


@curry
def post(session: requests.Session, url: str, data: str or dict) -> requests.Response:
    return session.post(url, data=data)


@curry
def startswith(string: str, substring: str) -> bool:
    return string.startswith(substring)


def get_missing_credits(session: requests.Session) -> dict:
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


def get_contacted_call_signs(session: requests.Session) -> list:
    qso_response = session.get('https://lotw.arrl.org/lotwuser/lotwreport.adi?qso_query=1&qso_withown=yes'
                               '&qso_qslsince=1900-01-01', stream=True)
    qso_text = ''.join([content.decode('utf-8') for content in qso_response.iter_content(chunk_size=1024)])
    return re.findall('^[<]CALL:[0-9][>](?P<call_sign>.*?)\r$', qso_text, flags=re.MULTILINE)


collect_arrl_data = concurrently(get_missing_credits, get_contacted_call_signs)


@curry
def get_call_sign_data(qrz_session: requests.Session, call_sign: str) -> dict:
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


@curry
def return_session_if_login_verified(session: requests.Session, response: requests.Response) -> requests.Session:
    return session if response.status_code == 200 else None


@curry
def login_to_lotw_arrl(session: requests.Session, call_sign: str, password: str) -> requests.Session:
    return chain(
        format_arrl_login_data,
        to(post(session=session, url='https://lotw.arrl.org/lotwuser/login'), kw='data'),
        to(return_session_if_login_verified(session=session), kw='response')
    )(call_sign, password)


@curry
def login_to_qrz(session: requests.Session, call_sign: str, password: str) -> requests.Session:
    return chain(
        format_qrz_login_data,
        to(post(session=session, url='https://www.qrz.com/login'), kw='data'),
        to(return_session_if_login_verified(session=session), kw='response')
    )((call_sign, password))


@curry
def handle_country(country: str, filter_func: callable, qrz_session: requests.Session) -> (str, list):
    return country[1], chain(
        filter_func,
        to(map(func=get_call_sign_data(qrz_session=qrz_session), kw='call_sign'), kw='iterable'),
    )(func=startswith(substring=country[0]))


@curry
def handle_arrl_data(contacted_call_signs: tuple, missing_countries: dict, qrz_session: requests.Session) -> dict:
    return chain(
        map(func=handle_country(filter_func=filterer(iterable=contacted_call_signs, kw='string'),
                                qrz_session=qrz_session),
            kw='country'),
        filter_empty_values,
        dict
    )(iterable=missing_countries.items())


def main(arrl_session: requests.Session, qrz_session: requests.Session) -> dict:
    return chain(
        collect_arrl_data,
        split_to(handle_arrl_data(qrz_session=qrz_session), kws=['missing_countries', 'contacted_call_signs'])
    )(session=arrl_session)


def setup(own_call_sign: str, arrl_pass: str, qrz_pass: str) -> (requests.Session, requests.Session):
    return chain(
        start_session,
        to(concurrently(
            login_to_lotw_arrl(password=arrl_pass, call_sign=own_call_sign),
            login_to_qrz(password=qrz_pass, call_sign=own_call_sign)
        ), kw='session')
    )()


if __name__ == "__main__":
    chain(
        setup,
        split_to(func=main, kws=('arrl_session', 'qrz_session')),
        pprint.pprint
    )(own_call_sign=input('Enter your Call Sign: '),
      arrl_pass=input('Enter your ARRL Password: '),
      qrz_pass=input('Enter your QRZ Password: '))

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
