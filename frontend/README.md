# 🎓 Big Data Club - Management System Frontend

A modern, responsive Next.js application for managing Big Data Club activities, projects, members, and events at HCMUT.

![Next.js](https://img.shields.io/badge/Next.js-15.5.9-000000?style=flat-square&logo=next.js)
![React](https://img.shields.io/badge/React-19.1.0-61DAFB?style=flat-square&logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-4.1.14-06B6D4?style=flat-square&logo=tailwindcss)

## ✨ Features

- 📱 **Responsive Design** - Seamless experience across all devices
- 🎨 **Modern UI** - Beautiful vintage-inspired interface with smooth animations
- 👥 **Member Management** - Showcase club members organized by teams
- 📊 **Project Showcase** - Display and manage featured projects
- 📰 **News & Publications** - Academic publications and club news
- 📅 **Event Management** - View and track club activities and events
- 🔐 **Authentication** - Secure login system with token-based auth
- 🌙 **Theme Support** - Light/Dark mode theme switching
- ⚡ **Performance** - Optimized with Turbopack for fast builds

## 🛠️ Tech Stack

- **Framework**: [Next.js 15.5](https://nextjs.org/) - React framework with App Router
- **Language**: [TypeScript](https://www.typescriptlang.org/) - Type-safe JavaScript
- **Styling**: [Tailwind CSS 4](https://tailwindcss.com/) - Utility-first CSS
- **UI Components**: [Radix UI](https://www.radix-ui.com/) - Headless components
- **Icons**: [Lucide React](https://lucide.dev/) & [React Icons](https://react-icons.github.io/react-icons/)
- **Animation**: [Framer Motion](https://www.framer.com/motion/)
- **Data Fetching**: [SWR](https://swr.vercel.app/) - React hooks for data fetching
- **State Management**: [Zustand](https://github.com/pmndrs/zustand)
- **Drag & Drop**: [@dnd-kit](https://docs.dndkit.com/)
- **Charts**: [Recharts](https://recharts.org/)
- **Notifications**: [React Hot Toast](https://react-hot-toast.com/)

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn package manager

### Installation

1. **Install dependencies:**
```bash
npm install
```

2. **Set up environment variables:**
```bash
cp .env.local.example .env.local
```

### Development Server

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the application. The page auto-reloads when you make changes.

## 📦 Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server with Turbopack |
| `npm run build` | Build optimized production bundle |
| `npm start` | Start production server |
| `npm run lint` | Run ESLint to check code quality |

## 📁 Project Structure

```
frontend/
├── src/
│   ├── app/                 # Next.js app directory
│   │   ├── (auth)/         # Authentication pages
│   │   ├── (landing)/      # Public landing pages
│   │   ├── (main)/         # Protected dashboard pages
│   │   └── api/            # API routes
│   ├── components/         # Reusable React components
│   ├── hooks/              # Custom React hooks
│   ├── services/           # API service layer
│   ├── store/              # Global state management
│   ├── utils/              # Utility functions
│   └── data/               # Static data (clubData.json)
├── public/                 # Static assets
└── package.json            # Dependencies
```

## 🔧 Configuration

### Customization

- **Theme Colors**: Edit `tailwind.config.ts`
- **Club Data**: Update `src/data/clubData.json`
- **Styling**: Modify component styles in `.tsx` files

## 📚 Key Pages

- `/` - Public landing page
- `/login` - Authentication page
- `/dashboard` - Main dashboard
- `/dashboard/events` - Event management
- `/dashboard/tasks` - Task board
- `/dashboard/leaderboard` - Member leaderboard
- `/projects/:id` - Project showcase

## 🔐 Authentication

The app uses JWT-based authentication with HTTP-only cookies for secure token storage.

## 🎨 Design

- **Color Scheme**: Vintage brown theme (#2c2416, #5a4a3a)
- **Font**: Geist Sans (default), Roboto Mono (mono)
- **Animations**: Framer Motion smooth transitions

## 🧪 Testing & Quality

```bash
npm run lint    # Run ESLint
```

## 📖 Resources

- [Next.js Docs](https://nextjs.org/docs)
- [React Docs](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [TypeScript](https://www.typescriptlang.org/docs/)

## 🚀 Deployment

### Vercel (Recommended)
1. Push to GitHub
2. Import in Vercel dashboard
3. Set environment variables
4. Deploy

### Docker
```bash
docker build -t bdc-frontend .
docker run -p 3000:3000 bdc-frontend
```

## 📝 Contributing

1. Create a feature branch
2. Make your changes
3. Commit and push
4. Open a Pull Request

## 📄 License

Part of Big Data Club @ HCMUT. All rights reserved.

---

**Built with ❤️ by Big Data Club Development Team**
