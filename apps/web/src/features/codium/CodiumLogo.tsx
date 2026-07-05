function ChannelWatchLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 256 256" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="channelWatchLogoStroke" x1="62" y1="62" x2="198" y2="194" gradientUnits="userSpaceOnUse">
          <stop stopColor="#F6F7F8" />
          <stop offset="1" stopColor="#D8DDE2" />
        </linearGradient>
      </defs>
      <rect width="256" height="256" rx="60" fill="#050607" />
      <rect x="22" y="22" width="212" height="212" rx="50" fill="#101113" />
      <rect x="22.5" y="22.5" width="211" height="211" rx="49.5" stroke="#F6F7F8" strokeOpacity="0.1" />
      <path
        d="M171 76C158 66 143 61 127 61C90.55 61 61 90.55 61 127C61 163.45 90.55 193 127 193C144 193 159.5 186.6 171.2 176.1"
        stroke="url(#channelWatchLogoStroke)"
        strokeLinecap="round"
        strokeWidth="30"
      />
      <path d="M151 127H199" stroke="#D8DDE2" strokeLinecap="round" strokeWidth="22" />
    </svg>
  );
}

export default ChannelWatchLogo;
