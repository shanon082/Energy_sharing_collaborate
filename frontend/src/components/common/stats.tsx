import Image from "next/image"
import directors from "@/assets/images/directors.webp"

export default function Stats () {

    const stats = [
        {
            data: "350M+",
            title: "Customers"
        },
        {
            data: "$10M+",
            title: "Commissions paid"
        },
        {
            data: "190+",
            title: "Countries"
        },
        {
            data: "$1BN",
            title: "Yearly revenue"
        },
    ]

    return (
        <section className="py-14 bg-white">
            <div className="max-w-screen-xl mx-auto px-4 text-gray-600 gap-x-12 items-start justify-between lg:flex md:px-8">
                <div className="sm:hidden lg:block lg:max-w-xl">
                    <Image width={600} height={300} src={directors} className="rounded-lg" alt="" />
                </div>
                <div className="mt-6 gap-12 sm:mt-0 md:flex lg:block">
                    <div className="max-w-2xl">
                        <h3 className="text-gray-800 text-3xl font-semibold sm:text-4xl">
                            We do our best to make customers always happy
                        </h3>
                        <p className="mt-3 max-w-xl">
                            Our customer is at the heartbeat of our business. We strive to ensure the best customer experiences all the time
                        </p>
                    </div>
                    <div className="flex-none mt-6 md:mt-0 lg:mt-6">
                        <ul className="inline-grid gap-y-8 gap-x-14 grid-cols-2">
                            {
                                stats.map((item, idx) => (
                                    <li key={idx} className="">
                                        <h4 className="text-4xl text-red-600 font-semibold">{item.data}</h4>
                                        <p className="mt-3 font-medium">{item.title}</p>
                                    </li>
                                ))
                            }
                        </ul>
                    </div>
                </div>
            </div>
        </section>
    )
}