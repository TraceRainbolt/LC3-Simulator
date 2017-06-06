# include <stdio.h>

void countBackwardFrom(int x);
void countForwardTo(int x);

int main() {
   int number;

   printf("Type a number to count to: ");
   scanf("%d", &number);
   countBackwardFrom(number);
   printf("\n");
   countForwardTo(number);
   printf("\n");

   return 0;
}

void countBackwardFrom(int x) {
   if (x <= 1) {
      printf("%d", x);
   } else {
      printf("%d, ", x);
      countBackwardFrom(x - 1);
   }
}

void countForwardTo(int x) {
   if (x == 1) {
      printf("%d", x);
   } else {
      countForwardTo(x - 1);
      printf(", %d", x);
   }
}
