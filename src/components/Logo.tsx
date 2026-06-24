import Image from "next/image";

interface LogoProps {
  className?: string;
  width?: number;
  height?: number;
}

export default function Logo({
  className = "",
  width = 400,
  height = 100,
}: LogoProps) {
  return (
    <div className={`relative flex items-center justify-center ${className}`}>
      <Image
        src="/logo/lepiverse-light.svg"
        alt="Lepiverse Logo"
        width={width}
        height={height}
        className="block dark:hidden w-full h-auto object-contain"
        priority
      />
      <Image
        src="/logo/lepiverse-dark.svg"
        alt="Lepiverse Logo"
        width={width}
        height={height}
        className="hidden dark:block w-full h-auto object-contain"
        priority
      />
    </div>
  );
}
