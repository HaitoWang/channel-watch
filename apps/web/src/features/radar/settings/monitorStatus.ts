/** Human-readable label for the QQBot gateway connection status. */
export function qqbotStatusLabel(status: string): string {
  return status === "connected"
    ? "已连接"
    : status === "connecting"
      ? "连接中"
      : status === "disabled"
        ? "未配置"
        : status === "error"
          ? "连接异常"
          : "未连接";
}
