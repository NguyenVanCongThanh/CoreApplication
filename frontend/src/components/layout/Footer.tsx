"use client"

import Link from 'next/link';
import { FaFacebook, FaTwitter, FaInstagram, FaLinkedin } from 'react-icons/fa';
import bdc from "@/assets/bdclogo.png"
import SafeImage from '../common/SafeImage';

const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-white border-t border-slate-200 w-full mt-auto flex-shrink-0">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-6 sm:gap-4">
          
          <Link 
            href="/" 
            className="flex items-center gap-3 group order-1"
          >
            <div className="relative w-8 h-8 rounded-lg overflow-hidden border border-slate-100 shadow-sm group-hover:shadow transition-shadow">
              <SafeImage
                src={bdc}
                alt="Big Data Club Logo"
                fill
                sizes="32px"
                className="object-cover"
              />
            </div>
            <span className="font-bold text-slate-900 tracking-tight group-hover:text-blue-600 transition-colors">
              BDC System
            </span>
          </Link>

          <span className="text-sm font-medium text-slate-500 order-3 sm:order-2 text-center">
            © 2025 - {currentYear} Big Data Club. All rights reserved.
          </span>

          {/* Right: Social Icons */}
          <div className="flex items-center gap-5 order-2 sm:order-3">
            {[
              { Icon: FaFacebook, href: "https://facebook.com/BDCofHCMUT", label: "Facebook" },
              { Icon: FaTwitter, href: "https://twitter.com", label: "Twitter" },
              { Icon: FaInstagram, href: "https://instagram.com", label: "Instagram" },
              { Icon: FaLinkedin, href: "https://linkedin.com", label: "LinkedIn" },
            ].map((social, idx) => (
              <a
                key={idx}
                href={social.href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={social.label}
                className="text-slate-400 hover:text-blue-600 hover:-translate-y-0.5 transition-all duration-300"
              >
                <social.Icon size={18} />
              </a>
            ))}
          </div>

        </div>
      </div>
    </footer>
  );
};

export default Footer;