# fetch_eastmoney_headers.py

from playwright.async_api import async_playwright
import asyncio


class EastmoneyKlineHeadersFetcher:
    def __init__(self):
        pass

    async def fetch_kline_headers(self, stock_url: str):
        """
        自动打开股票页面并拦截 K 线图数据请求，提取请求 Headers。

        :param stock_url: 东方财富个股页面地址，如:
                          https://quote.eastmoney.com/sh605005.html
        :return: headers 字典 或 None（失败时）
        """
        headers_result = None

        async def intercept_request(route, request):
            nonlocal headers_result
            if "qt/stock/kline/get" in request.url:
                headers_result = request.headers
                await route.continue_()
            else:
                await route.continue_()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                await context.route("**/api/qt/stock/kline/get*", intercept_request)

                page = await context.new_page()
                await page.goto(stock_url)

                # 给 JS 足够时间触发 API 请求
                await page.wait_for_timeout(10000)

                await context.close()
                await browser.close()

        except Exception as e:
            print(f"❌ 抓取失败 {stock_url}: {str(e)}")
            headers_result = None

        return headers_result

    async def batch_fetch_kline_headers(self, stock_urls):
        """
        批量抓取多个股票的 K 线请求 Headers。

        :param stock_urls: 股票页面 URL 列表
        :return: 列表，每项是对应股票的 headers 字典 或 None
        """
        tasks = [self.fetch_kline_headers(url) for url in stock_urls]
        results = await asyncio.gather(*tasks)
        return results

    # ======================
    # ✅ 示例入口函数
    # ======================


if __name__ == "__main__":
    async def main():
        # 示例股票列表
        stock_urls = [
            "https://quote.eastmoney.com/sh605005.html",
            "https://quote.eastmoney.com/sz300750.html",
            "https://quote.eastmoney.com/sh600000.html",
            "https://quote.eastmoney.com/sz002594.html"
        ]

        print("🚀 开始批量抓取请求头（Headers）...\n")
        eastmoneyKlineHeadersFetcher = EastmoneyKlineHeadersFetcher()

        headers_list = await eastmoneyKlineHeadersFetcher.batch_fetch_kline_headers(stock_urls)

        print("\n📊 所有股票抓取结果汇总：")
        for url, headers in zip(stock_urls, headers_list):
            print(f"\n🔗 股票页面: {url}")
            if headers:
                print("📎 全部 Headers:")
                for k, v in headers.items():
                    print(f"   {k}: {v}")
            else:
                print("❌ 未成功获取 Headers")


    asyncio.run(main())
