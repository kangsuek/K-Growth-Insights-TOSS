export default function Footer() {
  return (
    <footer className="bg-gray-800 text-white py-8 mt-auto" role="contentinfo">
      <div className="container mx-auto px-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <h3 className="font-semibold mb-2">K-Growth Insights TOSS</h3>
            <p className="text-sm text-gray-400">
              한국 ETF·주식 분석 앱 — 토스증권 Open API를 주 데이터 소스로 사용합니다.
            </p>
          </div>
          <div>
            <h3 className="font-semibold mb-2">데이터 소스</h3>
            <ul className="text-sm text-gray-400 space-y-1">
              <li>✓ 토스증권 Open API — 시세·캔들·매매동향·카탈로그</li>
              <li>✓ 네이버 — 펀더멘털·ETF·뉴스·지수 (예정)</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold mb-2">링크</h3>
            <a
              href="https://github.com/kangsuek/K-Growth-Insights-TOSS"
              target="_blank"
              rel="noreferrer"
              className="text-sm text-gray-400 hover:text-white"
            >
              GitHub 저장소
            </a>
          </div>
        </div>
        <div className="border-t border-gray-700 mt-6 pt-6 flex flex-col md:flex-row justify-between text-xs text-gray-500">
          <p>&copy; {new Date().getFullYear()} K-Growth Insights TOSS</p>
          <p>투자 판단의 참고 자료일 뿐이며, 투자 결과에 대한 책임은 이용자 본인에게 있습니다.</p>
        </div>
      </div>
    </footer>
  );
}
