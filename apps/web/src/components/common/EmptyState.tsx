interface Props {
  message: string;
  icon?: string;
}

export function EmptyState({ message, icon = '📭' }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-gray-500 text-sm">
      <span className="text-2xl mb-2">{icon}</span>
      <span>{message}</span>
    </div>
  );
}
