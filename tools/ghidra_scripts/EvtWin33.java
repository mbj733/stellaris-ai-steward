// EvtWin33: 扫描 0x1436a2b80..0x1436a2c80（方法对表）的引用——找消费方/执行器
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.util.LinkedHashSet;
import java.util.Set;

public class EvtWin33 extends GhidraScript {
    @Override
    public void run() throws Exception {
        Set<String> seen = new LinkedHashSet<>();
        for (long a = 0x1436a2b80L; a < 0x1436a2c80L; a += 4) {
            for (Reference r : getReferencesTo(toAddr(a))) {
                Function f = getFunctionContaining(r.getFromAddress());
                String line = r.getReferenceType() + " to 0x" + Long.toHexString(a)
                        + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                        + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?");
                if (seen.add(line)) {
                    println("  " + line);
                }
                if (seen.size() >= 40) {
                    println("  ...(capped)");
                    return;
                }
            }
        }
        println("total: " + seen.size());
        println("==== done ====");
    }
}
