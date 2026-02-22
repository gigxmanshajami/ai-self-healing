interface StatCardProps {
    title: string;
    value: string | number;
    change?: string;
    changeType?: 'positive' | 'negative' | 'neutral';
    icon: React.ReactNode;
    color: 'blue' | 'green' | 'purple' | 'orange';
}

const colorClasses = {
    blue: 'from-blue-500 to-blue-600',
    green: 'from-green-500 to-green-600',
    purple: 'from-purple-500 to-purple-600',
    orange: 'from-orange-500 to-orange-600',
};

const bgColorClasses = {
    blue: 'bg-blue-50',
    green: 'bg-green-50',
    purple: 'bg-purple-50',
    orange: 'bg-orange-50',
};

export default function StatCard({
    title,
    value,
    change,
    changeType = 'neutral',
    icon,
    color,
}: StatCardProps) {
    return (
        <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-sm font-medium text-gray-500">{title}</p>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
                    {change && (
                        <p
                            className={`text-sm mt-2 flex items-center gap-1 ${changeType === 'positive'
                                    ? 'text-green-600'
                                    : changeType === 'negative'
                                        ? 'text-red-600'
                                        : 'text-gray-500'
                                }`}
                        >
                            {changeType === 'positive' ? '↑' : changeType === 'negative' ? '↓' : ''}
                            {change}
                        </p>
                    )}
                </div>
                <div
                    className={`w-12 h-12 rounded-xl bg-gradient-to-br ${colorClasses[color]} flex items-center justify-center text-white shadow-lg`}
                >
                    {icon}
                </div>
            </div>
        </div>
    );
}
