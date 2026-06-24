interface RedListStatusProps {
  statusCode: string;
  horizontal?: boolean;
}

export function RedListStatus({ statusCode, horizontal = false }: RedListStatusProps) {
  let bgColor = "bg-deep-mocha-400";
  let textColor = "text-deep-mocha-900";
  let label = statusCode;
  switch (statusCode) {
    case "NE":
      bgColor = "bg-deep-mocha-300";
      textColor = "text-deep-mocha-900";
      label = "Not Evaluated";
      break;
    case "DD":
      bgColor = "bg-deep-mocha-200";
      textColor = "text-deep-mocha-900";
      label = "Data Deficient";
      break;
    case "LC":
      bgColor = "bg-green-200";
      textColor = "text-green-900";
      label = "Least Concern";
      break;
    case "NT":
      bgColor = "bg-yellow-200";
      textColor = "text-yellow-900";
      label = "Near Threatened";
      break;
    case "VU":
      bgColor = "bg-burnt-peach-200";
      textColor = "text-burnt-peach-900";
      label = "Vulnerable";
      break;
    case "EN":
      bgColor = "bg-orange-200";
      textColor = "text-orange-900";
      label = "Endangered";
      break;
    case "CR":
      bgColor = "bg-burnt-peach-300";
      textColor = "text-burnt-peach-900";
      label = "Critically Endangered";
      break;
    case "EX":
      bgColor = "bg-black";
      textColor = "text-white";
      label = "Extinct";
      break;
    case "EW":
      bgColor = "bg-deep-mocha-500";
      textColor = "text-white";
      label = "Extinct in the Wild";
      break;
  }
  if (horizontal) {
    return (
      <div className="flex flex-col items-start w-full px-4 py-4 gap-3 border border-deep-mocha-200 dark:border-deep-mocha-700 rounded-xl">
        <span className="text-2xl font-semibold">IUCN RedList</span>
        <span
          className={`px-2.5 py-0.5 rounded-full text-[11px] sm:text-xs font-medium ${bgColor} ${textColor}`}
          style={{ lineHeight: "1.25rem", display: "inline-flex", alignItems: "center" }}
        >
          {label}
        </span>
      </div>
    );
  }
  return (
    <div>
      <h2 className="text-2xl font-semibold mb-2">IUCN RedList Status</h2>
      <span
        className={`px-2 py-0.5 rounded-full text-xs font-medium ${bgColor} ${textColor}`}
      >
        {label}
      </span>
    </div>
  );
}
