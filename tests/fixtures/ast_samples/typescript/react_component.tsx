interface Props {
    title: string;
    onClick?: () => void;
}

export const Button: React.FC<Props> = ({ title, onClick }) => {
    return <button onClick={onClick}>{title}</button>;
};

export default function App() {
    return <Button title="Click me" />;
}
