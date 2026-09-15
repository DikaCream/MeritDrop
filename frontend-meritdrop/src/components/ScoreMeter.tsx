import { MERIT_BAR_BP } from "../config";

/**
 * A 20 segment gauge: filled segments are the score, the heavier notch is the
 * merit bar. Reads at a glance in a table cell without any chart library.
 */
export function ScoreMeter({ scoreBp, segments = 20 }: { scoreBp: number; segments?: number }) {
  const filled = Math.round((scoreBp / 10000) * segments);
  const barAt = Math.round((MERIT_BAR_BP / 10000) * segments);

  return (
    <span className="meter" aria-hidden="true">
      {Array.from({ length: segments }, (_, i) => {
        const classes = ["seg"];
        if (i < filled) classes.push("on");
        if (i === barAt) classes.push("bar");
        return <i key={i} className={classes.join(" ")} />;
      })}
    </span>
  );
}
