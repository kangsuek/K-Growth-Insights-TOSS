export default function ComingSoon({ title }) {
  return (
    <div className="animate-fadeIn">
      <h2 className="text-xl font-bold mb-4">{title}</h2>
      <div className="card-bordered text-center py-12 text-gray-500 dark:text-gray-400">
        준비 중입니다. 다음 마일스톤에서 구현될 예정입니다.
      </div>
    </div>
  );
}
