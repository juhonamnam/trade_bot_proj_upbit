import threading
from src.upbit.exchange_api import UpbitExchangeApi
from src.upbit.quotation_api import UpbitQuotationApi
import time
from src.telesk.app import Telesk
from src.resources import get_message


class RiseAlertThread(threading.Thread):

    def __init__(self, access, secret, telesk_app: Telesk):
        threading.Thread.__init__(self)
        self.upbit_quotation_api = UpbitQuotationApi()
        self.upbit_exchange_api = UpbitExchangeApi(access, secret)
        self.telesk_app = telesk_app
        self.sell_alert = dict()
        self.thread_alive = True
        self.thread_active = False
        self.daemon = True

    def run(self):
        self.thread_active = True

        while self.thread_alive:
            if self.thread_active:
                try:
                    balances = self.upbit_exchange_api.get_balances()
                    if not balances['ok']:
                        raise Exception(balances['description'])

                    avg_buy_prices = {x['unit_currency'] + '-' + x['currency']: x['avg_buy_price']
                                      for x in balances['data'] if x['currency'] != x['unit_currency']}

                    all_tickers = self.upbit_quotation_api.get_tickers()
                    if not all_tickers['ok']:
                        raise Exception(all_tickers['description'])

                    valid_tickers = all_tickers['data'].intersection(
                        avg_buy_prices.keys())

                    curr_prices = self.upbit_quotation_api.get_current_prices(
                        valid_tickers)
                    if not curr_prices['ok']:
                        raise Exception(curr_prices['description'])

                    curr_time = time.time()

                    for ticker in self.sell_alert.copy():
                        if ticker not in valid_tickers:
                            del self.sell_alert[ticker]

                    for ticker in valid_tickers:
                        intr = float(curr_prices['data'][ticker]) / \
                            float(avg_buy_prices[ticker]) - 1
                        intr = intr * 100

                        if ticker in self.sell_alert and self.sell_alert[ticker]['time'] + 1800 < curr_time and self.sell_alert[ticker]['interest'] > intr:
                            del self.sell_alert[ticker]

                        if ticker not in self.sell_alert and intr >= 5:
                            self.sell_alert[ticker] = {
                                'time': curr_time,
                                'interest': (intr // 5) * 5
                            }
                            self._send_alert(
                                ticker, self.sell_alert[ticker]['interest'])

                        elif ticker in self.sell_alert and intr >= self.sell_alert[ticker]['interest'] + 5:
                            self.sell_alert[ticker] = {
                                'time': curr_time,
                                'interest': (intr // 5) * 5
                            }
                            self._send_alert(
                                ticker, self.sell_alert[ticker]['interest'])

                except Exception as e:
                    self.telesk_app.logger.exception(e)
                    time.sleep(5)

            time.sleep(2)

        self.thread_active = False

    def end(self):
        self.thread_alive = False

    def _send_alert(self, ticker, intr):
        self.telesk_app.send_message_with_dict({
            'chat_id': self.telesk_app.config['one_user'],
            'text': get_message()('rise_alert').format(ticker=ticker, intr=intr)
        })
