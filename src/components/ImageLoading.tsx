import Image from "next/image";

function ImageLoading({ size }: { size: number }) {
  return (
    <div className="items-center justify-center text-center">
      <Image
        src="/leaflet/images/butterfly.svg"
        alt="Loading..."
        width={size}
        height={size}
        className="animate-pulse object-fill"
      />
      <p className="mt-2 flex items-baseline justify-center gap-2 text-xs text-baseline leading-none text-gray-500 mx-auto">
        <span className="text-sm">Loading image</span>
        <span className="flex items-center justify-center gap-1">
          <span className="-ml-1 w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:0ms]" />
          <span className="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:150ms]" />
          <span className="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:300ms]" />
        </span>
      </p>
    </div>
  );
}

export default ImageLoading;
