import { ReactNode } from "react";

interface MenuIconProps {
  icon: ReactNode;
  text: string;
}

export function IconMenu({ icon, text }: MenuIconProps) {
  return (
    <div className="flex items-center justify-between space-x-2">
      <p className="text-sm">{text}</p>
      {icon}
    </div>
  );
}