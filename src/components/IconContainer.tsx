function IconContainer({
  children,
  extendsClass = "",
}: {
  children: React.ReactNode;
  extendsClass?: string;
}) {
  return (
    <div
      className={`rounded-xl bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center p-2 mr-2 w-fit ${extendsClass}`}
    >
      {children}
    </div>
  );
}

export { IconContainer };
