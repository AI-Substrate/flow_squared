import { formatDate } from './utils';

interface DateDisplayProps {
    date: Date;
}

export function DateDisplay({ date }: DateDisplayProps) {
    // Cross-file function call - SolidLSP should detect this
    const formatted = formatDate(date);
    return <span>{formatted}</span>;
}
