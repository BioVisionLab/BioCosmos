interface RedListStatusProps {
  statusCode: string;
  horizontal?: boolean;
}

export function RedListStatus({ statusCode, horizontal = false }: RedListStatusProps) {
  let bgColor = "bg-gray-400";
  let textColor = "text-gray-900";
  let label = statusCode;
  switch (statusCode) {
    case "NE":
      bgColor = "bg-gray-300";
      textColor = "text-gray-900";
      label = "Not Evaluated";
      break;
    case "DD":
      bgColor = "bg-gray-200";
      textColor = "text-gray-900";
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
      bgColor = "bg-red-200";
      textColor = "text-red-900";
      label = "Vulnerable";
      break;
    case "EN":
      bgColor = "bg-orange-200";
      textColor = "text-orange-900";
      label = "Endangered";
      break;
    case "CR":
      bgColor = "bg-red-300";
      textColor = "text-red-900";
      label = "Critically Endangered";
      break;
    case "EX":
      bgColor = "bg-black";
      textColor = "text-white";
      label = "Extinct";
      break;
    case "EW":
      bgColor = "bg-gray-500";
      textColor = "text-white";
      label = "Extinct in the Wild";
      break;
  }
  if (horizontal) {
    return (
      <div className="flex flex-col items-start w-full px-5 py-5 gap-3 bg-gray-100 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl">
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
