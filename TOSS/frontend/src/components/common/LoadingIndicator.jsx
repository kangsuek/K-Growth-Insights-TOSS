export default function LoadingIndicator({
  size = "md",
  text = "데이터를 불러오는 중...",
  overlay = false,
}) {
  const sizeClass = { sm: "h-5 w-5", md: "h-8 w-8", lg: "h-12 w-12" }[size] || "h-8 w-8";

  const content = (
    <div className="flex flex-col items-center gap-2">
      <div className={`spinner ${sizeClass}`} />
      {text && <p className="text-sm text-gray-500 dark:text-gray-400">{text}</p>}
    </div>
  );

  if (!overlay) return content;

  return (
    <div className="fixed inset-0 bg-white dark:bg-gray-900 bg-opacity-90 flex items-center justify-center z-50">
      {content}
    </div>
  );
}
