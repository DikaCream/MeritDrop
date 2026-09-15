import { Link } from "react-router-dom";
import { Campaign } from "../lib/types";
import { formatCountdown, formatDate, formatGen, shortAddr } from "../config";

export function CampaignRow({ campaign }: { campaign: Campaign }) {
  const closed = campaign.status !== "OPEN";
  const fill = formatGen(campaign.allocated);

  return (
    <tr className="campaign-row">
      <td className="col-ref">#{campaign.id}</td>
      <td className="col-title">
        <Link to={`/campaigns/${campaign.id}`}>{campaign.title}</Link>
        <span className="sub">
          {shortAddr(campaign.sponsor)} · opened {formatDate(campaign.createdAt)}
        </span>
      </td>
      <td className="col-window">
        <span className="mono">{formatCountdown(campaign.closesAt)}</span>
        <span className="sub">closes {formatDate(campaign.closesAt)}</span>
      </td>
      <td className="col-num">{formatGen(campaign.budget, 2)}</td>
      <td className="col-num">{formatGen(campaign.escrow, 4)}</td>
      <td className="col-num strong">{fill}</td>
      <td className="col-num">{campaign.entryCount}</td>
      <td className="col-act">
        {closed ? (
          <span className="stamp ok">scored</span>
        ) : (
          <span className="stamp live">open</span>
        )}
      </td>
    </tr>
  );
}
