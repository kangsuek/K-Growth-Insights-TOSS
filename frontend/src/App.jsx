import { useQuery } from "@tanstack/react-query";
import { api } from "./services/api";

function useBackendHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data } = await api.get("/health");
      return data;
    },
  });
}

export default function App() {
  const { data, isLoading, isError } = useBackendHealth();

  let status = "확인 중...";
  if (isError) status = "백엔드 연결 실패";
  else if (data?.status === "ok") status = "백엔드 연결됨";

  return (
    <div style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>K-Growth Insights TOSS</h1>
      <p>{status}</p>
    </div>
  );
}
