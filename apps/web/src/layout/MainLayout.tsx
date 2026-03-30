import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { Board } from '../components/kanban/Board';

export function MainLayout() {
  return (
    <div className="h-screen w-screen bg-gray-950 flex flex-col overflow-hidden">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <main className="flex-1 overflow-hidden">
          <Board />
        </main>
        <Sidebar />
      </div>
    </div>
  );
}
