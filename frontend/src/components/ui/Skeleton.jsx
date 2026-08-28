// Loading state (master doc Section 3.4/4.1): skeleton cards instead of a
// blank screen or bare "Loading..." text while a request is in flight.
export function SkeletonLine({ className = "" }) {
  return <div className={`skeleton h-3 rounded ${className}`} />;
}

export function SkeletonCandidateCard() {
  return (
    <div className="bg-surface-2 border border-line rounded-2xl p-4 flex gap-4 items-center">
      <div className="skeleton w-16 h-16 rounded-full shrink-0" />
      <div className="flex-1 space-y-2.5">
        <SkeletonLine className="w-1/3" />
        <SkeletonLine className="w-1/5" />
        <div className="flex gap-1.5 pt-1">
          <div className="skeleton h-5 w-16 rounded-full" />
          <div className="skeleton h-5 w-20 rounded-full" />
          <div className="skeleton h-5 w-14 rounded-full" />
        </div>
      </div>
    </div>
  );
}

export function SkeletonStatCard() {
  return (
    <div className="bg-surface-2 border border-line rounded-2xl p-4 space-y-2">
      <SkeletonLine className="w-2/3" />
      <div className="skeleton h-7 w-1/3 rounded" />
    </div>
  );
}
